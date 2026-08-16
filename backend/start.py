#!/usr/bin/env python3
"""
start.py — Quick-start helper script for the SS SPARK backend.

Usage:
    python start.py

This script:
  1. Checks Python version (3.11+ required)
  2. Checks that .env exists
  3. Verifies key dependencies are installed
  4. Starts the Uvicorn server with hot-reload
"""

import sys
import subprocess
from pathlib import Path


def check_python():
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 11):
        print(f"[ERROR] Python 3.11+ required. Current: {sys.version}")
        sys.exit(1)
    print(f"[OK] Python {major}.{minor}")


def check_env():
    env_file = Path(".env")
    example = Path(".env.example")
    if not env_file.exists():
        if example.exists():
            import shutil
            shutil.copy(example, env_file)
            print("[WARN] .env not found — copied from .env.example")
            print("       -> Please open .env and fill in your API keys before continuing.\n")
        else:
            print("[WARN] .env file not found.")
    else:
        print("[OK] .env found")


def check_deps():
    required = ["fastapi", "uvicorn", "fitz", "pydantic_settings", "bcrypt", "jose"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("[WARN] Missing packages (run: pip install -r requirements.txt):")
        for m in missing:
            print(f"       - {m}")
    else:
        print("[OK] Core dependencies OK")


def start():
    print("\nStarting SS SPARK Backend ...\n")
    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
            "--log-level", "info",
        ],
        check=True,
    )


if __name__ == "__main__":
    print("=" * 50)
    print("  SS SPARK Backend — Pre-flight Checks")
    print("=" * 50)
    check_python()
    check_env()
    check_deps()
    print()
    start()
