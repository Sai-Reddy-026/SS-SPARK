import os
import litellm
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = key
os.environ["GOOGLE_API_KEY"] = key

candidate_models = [
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-flash-lite",
    "gemini/gemini-3.5-flash",
    "gemini/gemini-3.7-flash",
    "gemini/gemini-flash-latest",
    "gemini/gemini-flash-lite-latest",
]

print("Testing Gemini Models with LiteLLM...")
for model in candidate_models:
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "What is DBMS in 1 sentence?"}],
        )
        answer = response.choices[0].message.content.strip()
        print(f"[SUCCESS] {model}: {answer[:90]}...")
    except Exception as exc:
        print(f"[FAIL] {model}: {exc}")
