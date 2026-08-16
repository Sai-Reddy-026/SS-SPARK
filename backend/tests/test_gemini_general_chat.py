import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Set env keys
key = os.getenv("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = key
os.environ["GOOGLE_API_KEY"] = key

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from rag.general_llm import general_chat

async def test():
    print("Testing general_chat with 'what is meant by dbms'...")
    res = await general_chat(question="what is meant by dbms")
    print("Status:", res.get("status"))
    print("Answer:\n", res.get("answer"))

if __name__ == "__main__":
    asyncio.run(test())
