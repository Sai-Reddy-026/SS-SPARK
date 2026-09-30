"""
api/provider_status.py

Admin-only endpoint for AI Provider Router metrics.

GET  /api/admin/providers          — list all provider states (no API keys exposed)
POST /api/admin/providers/{name}/reset  — manually clear a provider's cooldown
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_admin

logger = logging.getLogger("ss_spark.provider_status_api")
router = APIRouter(
    prefix="/api/admin/providers",
    tags=["Admin", "AI Providers"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("")
async def list_provider_status():
    """
    Return runtime metrics for all AI providers.
    Metrics include: availability, EWMA latency, request counts, cooldown state.
    API keys are NEVER included in the response.
    """
    try:
        from rag.provider_router import get_router
        router_instance = get_router()
        providers = router_instance.get_status()
        mode = router_instance.routing_mode()
        timeout = router_instance.request_timeout()
        cooldown = float(os.getenv("AI_PROVIDER_COOLDOWN_SECONDS", "30"))

        return {
            "success": True,
            "data": {
                "routing_mode": mode,
                "request_timeout_s": timeout,
                "cooldown_s": cooldown,
                "providers": providers,
            },
        }
    except Exception as exc:
        logger.exception("Failed to fetch provider status: %s", exc)
        raise HTTPException(status_code=500, detail="Could not retrieve provider status.")


@router.post("/{provider_name}/reset")
async def reset_provider(provider_name: str):
    """
    Manually clear the cooldown and failure counters for a provider.
    Useful when a provider was temporarily rate-limited but is now available.
    """
    try:
        from rag.provider_router import get_router
        router_instance = get_router()
        ok = router_instance.reset_provider(provider_name)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider_name}' not found. Valid names: gemini, openai, nvidia, openrouter, custom.",
            )
        return {
            "success": True,
            "message": f"Provider '{provider_name}' cooldown cleared and failure counters reset.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to reset provider %s: %s", provider_name, exc)
        raise HTTPException(status_code=500, detail="Could not reset provider.")


@router.get("/routing-mode")
async def get_routing_mode():
    """Return current routing mode and timeout configuration."""
    return {
        "success": True,
        "data": {
            "routing_mode": os.getenv("AI_ROUTING_MODE", "fast"),
            "request_timeout_s": float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "8")),
            "cooldown_s": float(os.getenv("AI_PROVIDER_COOLDOWN_SECONDS", "30")),
            "note": (
                "Set AI_ROUTING_MODE=race to enable parallel racing (consumes quota from all providers). "
                "Default is 'fast' (sequential, lowest latency first)."
            ),
        },
    }
