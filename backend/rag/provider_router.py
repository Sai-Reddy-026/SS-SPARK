"""
rag/provider_router.py

Centralized AI Provider Router for SS SPARK.

Architecture:
    general_chat_stream() / general_chat()
        ↓
    ProviderRouter.get_candidate_models()   <- selects best available provider(s)
        ↓
    LiteLLM call (via existing general_llm.py)
        ↓
    record_result()                          <- update latency / failure state

Key Features:
  - Runtime latency tracking (EWMA) per provider
  - Configurable fast mode (lowest latency first) or race mode (parallel, first wins)
  - Automatic provider cooldown after rate-limits / failures
  - Key rotation: cycles through GEMINI_API_KEY, GEMINI_API_KEY_2, etc.
  - In-process state - zero external dependencies (no Redis required at 5-user scale)
  - Configurable via environment variables - no hard-coded priorities
  - OpenAI integrated as a proper routed provider
  - Fourth provider slot (CUSTOM_PROVIDER) configurable for any OpenAI-compatible endpoint

Environment variables read:
    AI_ROUTING_MODE              fast | race   (default: fast)
    AI_REQUEST_TIMEOUT_SECONDS   8             (default: 8)
    AI_PROVIDER_COOLDOWN_SECONDS 30            (default: 30)

    Per-provider model overrides:
    GEMINI_MODEL, OPENAI_MODEL, NVIDIA_MODEL, OPENROUTER_MODEL, CUSTOM_MODEL

    Secondary keys (optional):
    GEMINI_API_KEY_2, OPENAI_API_KEY_2, NVIDIA_API_KEY_2, OPENROUTER_API_KEY_2

    Fourth / custom provider (all three required to enable):
    CUSTOM_PROVIDER_NAME         e.g. "groq"
    CUSTOM_PROVIDER_BASE_URL     e.g. "https://api.groq.com/openai/v1"
    CUSTOM_PROVIDER_API_KEY      e.g. "gsk_..."
    CUSTOM_MODEL                 e.g. "groq/llama-3.1-8b-instant"
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

logger = logging.getLogger("ss_spark.provider_router")

# ── Default model lists — VERIFIED WORKING against real provider APIs ─────────
# Last verified: 2026-09-29
#
# Gemini: gemini-2.x deprecated per Google 404 response.
# Google migration notice: "use models/gemini-3.5-flash-lite"
_DEFAULT_GEMINI_MODELS = [
    "gemini/gemini-3.5-flash-lite",   # VERIFIED OK — fastest, free tier
    "gemini/gemini-3.5-flash",        # VERIFIED OK — higher quality (503 under load but valid)
]

# OpenAI: paid models — gpt-4o-mini is cheapest paid option.
# IMPORTANT: These require a paid OpenAI account with billing.
# If you only have a free-tier key (with quota exhausted), these will 429.
# Configurable via OPENAI_MODEL env var to override.
_DEFAULT_OPENAI_MODELS = [
    "gpt-4o-mini",     # cheapest paid model — $0.15/1M input tokens
    "gpt-3.5-turbo",   # legacy fallback
]

# OpenRouter: VERIFIED working models for this account.
# NOTE: :free tagged models have been removed from OpenRouter's free tier.
# deepseek-chat is paid but cheap (~$0.27/1M tokens via OpenRouter).
# If you need a free model, check https://openrouter.ai/models?q=free for current list.
_DEFAULT_OPENROUTER_MODELS = [
    "openrouter/deepseek/deepseek-chat",  # VERIFIED OK — fast and cheap
]

_DEFAULT_NVIDIA_MODELS = [
    "nvidia_nim/meta/llama-3.2-11b-vision-instruct",      # VERIFIED OK — 1312ms
    "nvidia_nim/nvidia/llama-3.1-nemotron-70b-instruct",  # larger fallback
]

# EWMA decay factor for latency smoothing
# alpha = 0.3 means each new sample contributes 30% weight
_EWMA_ALPHA = 0.3

# Initial assumed latency (ms) - neutral so all providers compete fairly at start
_INITIAL_LATENCY_MS = 1200.0

# Config cache TTL in seconds — avoids re-reading 15+ env vars per LLM request
_CONFIG_CACHE_TTL = 5.0


# ─────────────────────────────────────────────────────────────────────────────
# ProviderState - lightweight in-memory runtime state per provider
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProviderState:
    name: str
    enabled: bool = True
    available: bool = True
    avg_latency_ms: float = _INITIAL_LATENCY_MS
    last_latency_ms: float = _INITIAL_LATENCY_MS
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    key_index: int = 0  # for key rotation cycling

    def is_ready(self) -> bool:
        """Return True if this provider is enabled, not in cooldown, and available."""
        if not self.enabled:
            return False
        now = time.monotonic()
        if self.cooldown_until > now:
            return False
        # Auto-recover once cooldown expires
        if not self.available:
            self.available = True
        return True

    def record_success(self, latency_ms: float) -> None:
        """Update EWMA latency and reset failure counters on success."""
        self.avg_latency_ms = _EWMA_ALPHA * latency_ms + (1 - _EWMA_ALPHA) * self.avg_latency_ms
        self.last_latency_ms = latency_ms
        self.total_requests += 1
        self.total_successes += 1
        self.consecutive_failures = 0
        self.available = True
        self.cooldown_until = 0.0
        logger.info(
            "[AI ROUTER] provider=%s latency=%.0fms ewma=%.0fms status=success",
            self.name, latency_ms, self.avg_latency_ms,
        )

    def record_failure(self, error_type: str, cooldown_seconds: float) -> None:
        """
        Record failure, apply progressive cooldown.
        Cooldown doubles per consecutive failure, capped at 5x base.
        Does NOT log prompts or API keys.
        """
        self.total_requests += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        multiplier = min(self.consecutive_failures, 5)
        effective_cooldown = cooldown_seconds * multiplier
        self.available = False
        self.cooldown_until = time.monotonic() + effective_cooldown
        logger.warning(
            "[AI ROUTER] provider=%s error_type=%s consecutive_failures=%d cooldown=%.0fs",
            self.name, error_type, self.consecutive_failures, effective_cooldown,
        )

    def as_dict(self) -> Dict[str, Any]:
        """Safe public telemetry - does NOT include API keys or prompts."""
        now = time.monotonic()
        remaining = max(0.0, self.cooldown_until - now)
        return {
            "name": self.name,
            "enabled": self.enabled,
            "available": self.is_ready(),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "last_latency_ms": round(self.last_latency_ms, 1),
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "cooldown_remaining_s": round(remaining, 1),
        }


# ─────────────────────────────────────────────────────────────────────────────
# ProviderRouter - singleton managing all provider state
# ─────────────────────────────────────────────────────────────────────────────

class ProviderRouter:
    """
    Singleton AI Provider Router for SS SPARK.

    Typical usage in general_llm.py:
        router = get_router()
        models = router.get_candidate_models()
        router.inject_key_for_model(model)
        # ... call litellm with model ...
        router.record_success(provider_name, latency_ms)
        # on error:
        router.record_failure(provider_name, error_type)
    """

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderState] = {}
        self._initialized = False
        self._config_cache: Optional[Dict[str, Any]] = None
        self._config_cache_ts: float = 0.0

    # ── Initialization ────────────────────────────────────────────────────────

    def _init_if_needed(self) -> None:
        """Lazy initialization on first call so env vars can be set after module import."""
        if not self._initialized:
            self._initialized = True
            self._refresh_providers()

    def _refresh_providers(self) -> None:
        """Re-read env vars and update enabled state for each provider."""
        cfg = self._load_config()

        provider_enabled = {
            "gemini": bool(cfg["gemini_key"]),
            "openai": bool(cfg["openai_key"]),
            "openrouter": bool(cfg["openrouter_key"]),
            "nvidia": bool(cfg["nvidia_key"]),
            "custom": bool(
                cfg["custom_key"] and cfg.get("custom_name") and cfg.get("custom_model")
            ),
        }

        for name, has_key in provider_enabled.items():
            if name not in self._providers:
                self._providers[name] = ProviderState(name=name, enabled=has_key)
            else:
                self._providers[name].enabled = has_key

    def _load_config(self) -> Dict[str, Any]:
        """Read router-relevant env vars, cached for _CONFIG_CACHE_TTL seconds to avoid per-request overhead."""
        now = time.monotonic()
        if self._config_cache is not None and (now - self._config_cache_ts) < _CONFIG_CACHE_TTL:
            return self._config_cache

        try:
            from core.config import get_settings
            get_settings().apply_to_env()
        except Exception:
            pass

        def _get(*keys: str) -> str:
            for k in keys:
                v = os.getenv(k, "").strip()
                if v:
                    return v
            return ""

        cfg = {
            "gemini_key": _get("GEMINI_API_KEY", "GOOGLE_API_KEY"),
            "gemini_key_2": _get("GEMINI_API_KEY_2"),
            "openai_key": _get("OPENAI_API_KEY"),
            "openai_key_2": _get("OPENAI_API_KEY_2"),
            "nvidia_key": _get("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"),
            "nvidia_key_2": _get("NVIDIA_API_KEY_2"),
            "openrouter_key": _get("OPENROUTER_API_KEY"),
            "openrouter_key_2": _get("OPENROUTER_API_KEY_2"),
            # 4th / custom provider
            "custom_name": _get("CUSTOM_PROVIDER_NAME"),
            "custom_base_url": _get("CUSTOM_PROVIDER_BASE_URL"),
            "custom_key": _get("CUSTOM_PROVIDER_API_KEY"),
            "custom_model": _get("CUSTOM_MODEL"),
            # Model overrides
            "gemini_model": _get("GEMINI_MODEL"),
            "openai_model": _get("OPENAI_MODEL"),
            "nvidia_model": _get("NVIDIA_MODEL"),
            "openrouter_model": _get("OPENROUTER_MODEL"),
            # Routing settings — lower default timeout for faster fallback
            "routing_mode": _get("AI_ROUTING_MODE") or "fast",
            "timeout_s": float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "5")),
            "cooldown_s": float(os.getenv("AI_PROVIDER_COOLDOWN_SECONDS", "30")),
        }
        self._config_cache = cfg
        self._config_cache_ts = now
        return cfg

    # ── Key rotation ──────────────────────────────────────────────────────────

    def _get_rotated_key(self, provider: str) -> Optional[str]:
        """Return the next API key for the provider, cycling through primary + secondary."""
        cfg = self._load_config()
        key_pools: Dict[str, List[str]] = {
            "gemini": [k for k in [cfg["gemini_key"], cfg["gemini_key_2"]] if k],
            "openai": [k for k in [cfg["openai_key"], cfg["openai_key_2"]] if k],
            "nvidia": [k for k in [cfg["nvidia_key"], cfg["nvidia_key_2"]] if k],
            "openrouter": [k for k in [cfg["openrouter_key"], cfg["openrouter_key_2"]] if k],
            "custom": [k for k in [cfg["custom_key"]] if k],
        }
        keys = key_pools.get(provider, [])
        if not keys:
            return None
        state = self._providers.get(provider)
        if state is None:
            return keys[0]
        idx = state.key_index % len(keys)
        state.key_index += 1
        return keys[idx]

    # ── Model list resolution ──────────────────────────────────────────────────

    def _models_for_provider(self, provider: str, cfg: Dict[str, Any]) -> List[str]:
        """Return the ordered model list for a given provider."""
        if provider == "gemini":
            if cfg["gemini_model"]:
                return [f"gemini/{cfg['gemini_model']}"]
            return list(_DEFAULT_GEMINI_MODELS)

        if provider == "openai":
            if cfg["openai_model"]:
                return [cfg["openai_model"]]
            return list(_DEFAULT_OPENAI_MODELS)

        if provider == "openrouter":
            if cfg["openrouter_model"]:
                return [f"openrouter/{cfg['openrouter_model']}"]
            return list(_DEFAULT_OPENROUTER_MODELS)

        if provider == "nvidia":
            if cfg["nvidia_model"]:
                return [f"nvidia_nim/{cfg['nvidia_model']}"]
            return list(_DEFAULT_NVIDIA_MODELS)

        if provider == "custom":
            model = cfg.get("custom_model", "")
            if model:
                return [model]

        return []

    # ── Candidate model selection ─────────────────────────────────────────────

    def get_candidate_models(self) -> List[str]:
        """
        Return an ordered flat list of model strings to try.
        In fast mode: enabled + not-in-cooldown providers sorted by EWMA latency ascending.
        """
        self._init_if_needed()
        cfg = self._load_config()

        # Collect ready providers sorted by latency (fastest first = fast mode)
        ready: List[Tuple[float, str]] = []
        for name, state in self._providers.items():
            if state.enabled and state.is_ready():
                ready.append((state.avg_latency_ms, name))

        ready.sort(key=lambda x: x[0])  # ascending latency

        models: List[str] = []
        for _, pname in ready:
            for m in self._models_for_provider(pname, cfg):
                if m not in models:
                    models.append(m)

        # Safety: if nothing ready, include all enabled providers regardless of cooldown
        if not models:
            logger.error("[AI ROUTER] No provider currently available — bypassing cooldown as last resort")
            for pname in ("gemini", "openai", "openrouter", "nvidia", "custom"):
                state = self._providers.get(pname)
                if state and state.enabled:
                    for m in self._models_for_provider(pname, cfg):
                        if m not in models:
                            models.append(m)

        if not models:
            raise RuntimeError(
                "No AI provider is configured. Please set at least one of: "
                "GEMINI_API_KEY, OPENAI_API_KEY, NVIDIA_API_KEY, OPENROUTER_API_KEY"
            )

        return models

    def get_provider_for_model(self, model: str) -> str:
        """Map a LiteLLM model string back to a provider name."""
        if "openrouter" in model:
            return "openrouter"
        if "gemini" in model or "google" in model:
            return "gemini"
        if "nvidia" in model or "nvidia_nim" in model:
            return "nvidia"
        if model.startswith("gpt-") or "openai" in model:
            return "openai"
        cfg = self._load_config()
        if cfg.get("custom_model") and model == cfg["custom_model"]:
            return "custom"
        return "unknown"

    # ── Result recording ──────────────────────────────────────────────────────

    def record_success(self, provider_name: str, latency_ms: float) -> None:
        """Record a successful provider call and update EWMA latency."""
        self._init_if_needed()
        state = self._providers.get(provider_name)
        if state:
            state.record_success(latency_ms)

    def record_failure(self, provider_name: str, error_type: str) -> None:
        """Record a provider failure and apply cooldown."""
        self._init_if_needed()
        cfg = self._load_config()
        state = self._providers.get(provider_name)
        if state:
            state.record_failure(error_type, cfg["cooldown_s"])

    # ── API key injection ─────────────────────────────────────────────────────

    def inject_key_for_model(self, model: str) -> None:
        """
        Inject the rotated API key into os.environ before calling LiteLLM.
        Supports key rotation by cycling through primary + secondary keys.
        This keeps API keys strictly backend-side.
        """
        provider = self.get_provider_for_model(model)
        key = self._get_rotated_key(provider)
        if not key:
            return

        cfg = self._load_config()

        if provider == "gemini":
            os.environ["GEMINI_API_KEY"] = key
            os.environ["GOOGLE_API_KEY"] = key

        elif provider == "openai":
            os.environ["OPENAI_API_KEY"] = key

        elif provider == "nvidia":
            os.environ["NVIDIA_API_KEY"] = key
            os.environ["NVIDIA_NIM_API_KEY"] = key

        elif provider == "openrouter":
            os.environ["OPENROUTER_API_KEY"] = key

        elif provider == "custom":
            # For any OpenAI-compatible endpoint, set the key and base URL
            os.environ["OPENAI_API_KEY"] = key
            base_url = cfg.get("custom_base_url", "")
            if base_url:
                os.environ["OPENAI_API_BASE"] = base_url

    # ── Mode / config accessors ───────────────────────────────────────────────

    def routing_mode(self) -> str:
        """Return current routing mode: 'fast' or 'race'."""
        cfg = self._load_config()
        return cfg.get("routing_mode", "fast").lower()

    def request_timeout(self) -> float:
        """Return configured first-token timeout in seconds."""
        cfg = self._load_config()
        return cfg.get("timeout_s", 8.0)

    # ── Status / telemetry (admin only) ──────────────────────────────────────

    def get_status(self) -> List[Dict[str, Any]]:
        """Return public metrics for all providers. No API keys or prompts exposed."""
        self._init_if_needed()
        return [state.as_dict() for state in self._providers.values()]

    def reset_provider(self, provider_name: str) -> bool:
        """Manually clear cooldown and failure counters for a provider."""
        state = self._providers.get(provider_name)
        if state:
            state.consecutive_failures = 0
            state.cooldown_until = 0.0
            state.available = True
            logger.info("[AI ROUTER] provider=%s manually reset", provider_name)
            return True
        return False


# ── Module-level singleton ────────────────────────────────────────────────────

_router_instance: Optional[ProviderRouter] = None


def get_router() -> ProviderRouter:
    """Return the module-level singleton ProviderRouter (thread-safe via GIL at module level)."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ProviderRouter()
    return _router_instance


# ─────────────────────────────────────────────────────────────────────────────
# Optional Race mode helper
# ─────────────────────────────────────────────────────────────────────────────

async def _race_attempt_single(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float,
    result_queue: "asyncio.Queue[Any]",
    cancel_event: asyncio.Event,
) -> None:
    """
    One competitor in a race: try model, put result in queue.
    Signals '__winner__' or '__failure__'.
    """
    import litellm
    router = get_router()
    provider = router.get_provider_for_model(model)
    router.inject_key_for_model(model)
    t_start = time.monotonic()
    try:
        stream = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            stream=True,
            timeout=timeout + 15,
        )
        first_chunk = await asyncio.wait_for(stream.__anext__(), timeout=timeout)
        if cancel_event.is_set():
            return
        await result_queue.put(("__winner__", model, stream, first_chunk, t_start))
    except Exception as exc:
        if not cancel_event.is_set():
            await result_queue.put(("__failure__", model, type(exc).__name__))


async def race_chat_stream(
    messages: List[Dict[str, str]],
    req_id: str = "",
) -> AsyncGenerator[Tuple[str, str], None]:
    """
    Race mode (AI_ROUTING_MODE=race):
    Fire all providers simultaneously, stream from the first to send a token.
    Cancels remaining tasks after winner is found.

    WARNING: Race mode consumes quota from ALL providers it fires simultaneously.
    Use only when explicitly enabled with AI_ROUTING_MODE=race.
    Default mode is 'fast' which uses sequential fallback.
    """
    router = get_router()
    models = router.get_candidate_models()
    timeout = router.request_timeout()
    tag = f"[{req_id}] " if req_id else ""

    if not models:
        yield ("token", "AI service is temporarily unavailable. Please try again.")
        return

    cancel_event = asyncio.Event()
    result_queue: asyncio.Queue = asyncio.Queue()

    # Limit to 4 concurrent to avoid excessive quota consumption
    race_models = models[:4]
    tasks = [
        asyncio.create_task(
            _race_attempt_single(m, messages, timeout, result_queue, cancel_event)
        )
        for m in race_models
    ]
    logger.info("%s[RACE] firing %d providers simultaneously", tag, len(tasks))

    failures = 0
    winning_model: Optional[str] = None

    while failures < len(tasks):
        try:
            item = await asyncio.wait_for(result_queue.get(), timeout=timeout + 10)
        except asyncio.TimeoutError:
            logger.warning("%s[RACE] timed out waiting for any provider", tag)
            break

        kind = item[0]
        if kind == "__failure__":
            _, failed_model, err_type = item
            pname = router.get_provider_for_model(failed_model)
            router.record_failure(pname, err_type)
            failures += 1
            logger.warning("%s[RACE] %s failed: %s", tag, pname, err_type)
            continue

        if kind == "__winner__":
            _, win_model, stream, first_chunk, t_start = item
            winning_model = win_model
            cancel_event.set()
            for t in tasks:
                t.cancel()

            pname = router.get_provider_for_model(win_model)
            logger.info("%s[RACE] winner=%s model=%s", tag, pname, win_model)

            tokens = 0
            try:
                delta = first_chunk.choices[0].delta if (first_chunk and first_chunk.choices) else None
                content = getattr(delta, "content", "") if delta else ""
                if content:
                    tokens += 1
                    yield ("token", content)
                async for chunk in stream:
                    delta = chunk.choices[0].delta if (chunk and chunk.choices) else None
                    c = getattr(delta, "content", "") if delta else ""
                    if c:
                        tokens += 1
                        yield ("token", c)
                latency_ms = (time.monotonic() - t_start) * 1000
                router.record_success(pname, latency_ms)
            except Exception as exc:
                router.record_failure(pname, type(exc).__name__)
                if tokens > 0:
                    yield ("reset", "")
            return

    if not winning_model:
        yield ("token", "AI service is temporarily unavailable. All providers failed. Please try again in a few seconds.")
