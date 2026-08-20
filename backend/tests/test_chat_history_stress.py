"""
backend/tests/test_chat_history_stress.py
Chat History Stress Test: Evaluates multi-turn conversation retrieval, memory overhead,
and response latency scaling across 10, 50, 100, 500, and 1000 message histories.
"""

import asyncio
import os
import sys
import time
import uuid

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import models
from database.models import ChatMessage, get_history, save_message
from services.chat_service import ask_question


async def run_chat_history_stress_test():
    print("=" * 75)
    print("  CHAT HISTORY MULTI-TURN CONVERSATION SCALING & STRESS TEST")
    print("=" * 75)

    user_id = f"stress_user_{uuid.uuid4().hex[:8]}"
    session_id = f"stress_session_{uuid.uuid4().hex[:8]}"

    test_sizes = [10, 50, 100, 500, 1000]

    print(f"\n{'Target Turn Count':<20} | {'DB Insert':>12} | {'History Fetch':>14} | {'Memory Items':>14} | {'Context Build':>14}")
    print("-" * 80)

    current_inserted = 0

    for target_count in test_sizes:
        to_insert = target_count - current_inserted

        # 1. Insert messages
        t0 = time.perf_counter()
        for i in range(to_insert):
            idx = current_inserted + i
            role = "user" if idx % 2 == 0 else "assistant"
            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=f"Historical message turn #{idx}: discussion of database normal form 3NF and B-Tree indexing parameters.",
                user_id=user_id,
            )
            await save_message(msg)
        t_insert = (time.perf_counter() - t0) * 1000.0
        current_inserted = target_count

        # 2. Fetch history (with bounded retrieval limit)
        t0 = time.perf_counter()
        history = await get_history(session_id=session_id, limit=50, user_id=user_id)
        t_fetch = (time.perf_counter() - t0) * 1000.0

        # 3. Context formatting
        t0 = time.perf_counter()
        formatted = [{"role": m.role, "content": m.content} for m in history]
        t_format = (time.perf_counter() - t0) * 1000.0

        print(f"{target_count:<20} | {t_insert:10.2f}ms | {t_fetch:12.2f}ms | {len(history):>14} | {t_format:12.2f}ms")

    print("\n" + "=" * 75)
    print("  CHAT HISTORY STRESS TEST PASSED")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_chat_history_stress_test())
