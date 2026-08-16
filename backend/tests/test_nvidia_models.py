import os
import litellm
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("NVIDIA_API_KEY")
os.environ["NVIDIA_API_KEY"] = key
os.environ["NVIDIA_NIM_API_KEY"] = key

candidate_models = [
    "nvidia_nim/meta/llama-3.1-70b-instruct",
    "nvidia_nim/meta/llama-3.3-70b-instruct",
    "nvidia_nim/meta/llama-3.1-8b-instruct",
    "nvidia_nim/mistralai/mistral-large-2-instruct",
    "nvidia_nim/nvidia/llama-3.1-nemotron-70b-instruct",
]

print("Testing NVIDIA NIM models...")
for model in candidate_models:
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Hello in 3 words"}],
        )
        answer = response.choices[0].message.content.strip()
        print(f"[SUCCESS] {model}: {answer}")
    except Exception as exc:
        print(f"[FAIL] {model}: {exc}")
