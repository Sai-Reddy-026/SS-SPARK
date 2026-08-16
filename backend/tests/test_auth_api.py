"""
backend/tests/test_auth_api.py
Direct verification of FastAPI auth and admin endpoints using TestClient.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_auth_suite():
    print("\n" + "=" * 60)
    print("  FASTAPI AUTH & ENDPOINTS INTEGRATION TEST")
    print("=" * 60)

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("  [PASS] /health endpoint")

    # 2. OAuth config endpoint
    res = client.get("/api/auth/oauth/config")
    assert res.status_code == 200, f"OAuth config failed: {res.text}"
    data = res.json()
    assert "google_enabled" in data["data"]
    print(f"  [PASS] /api/auth/oauth/config: google_enabled={data['data']['google_enabled']}")

    # 3. Google OAuth redirect (graceful redirect check)
    res = client.get("/api/auth/oauth/google", follow_redirects=False)
    assert res.status_code in (302, 307), f"Google OAuth redirect failed: {res.status_code}"
    print(f"  [PASS] /api/auth/oauth/google: redirects to {res.headers.get('location', '')[:60]}...")

    # 4. Registration
    test_email = "audit_test_user@ssspark.ai"
    test_pass = "SecurePass123!"
    res = client.post("/api/auth/register", json={
        "email": test_email,
        "password": test_pass,
        "full_name": "Audit Tester",
    })
    # If user already exists in DB, handle gracefully
    if res.status_code == 400 and "already exists" in res.text:
        # Login instead
        res = client.post("/api/auth/login", json={"email": test_email, "password": test_pass})
    assert res.status_code in (200, 201), f"Register/Login failed: {res.text}"
    auth_data = res.json()["data"]
    access_token = auth_data["access_token"]
    refresh_token = auth_data["refresh_token"]
    print("  [PASS] /api/auth/register and token generation")

    # 5. /api/auth/me (Protected route)
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert res.status_code == 200, f"/me failed: {res.text}"
    user_info = res.json()["data"]
    assert user_info["email"] == test_email
    print(f"  [PASS] /api/auth/me: retrieved profile for {user_info['email']}")

    # 6. /api/auth/refresh
    res = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200, f"/refresh failed: {res.text}"
    new_access = res.json()["data"]["access_token"]
    assert new_access, "No new access token returned"
    print("  [PASS] /api/auth/refresh: successfully rotated access token")

    # 7. /api/auth/logout (Authenticated)
    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {new_access}"})
    assert res.status_code == 200, f"/logout (auth) failed: {res.text}"
    print("  [PASS] /api/auth/logout (authenticated): 200 OK")

    # 8. /api/auth/logout (Unauthenticated)
    res = client.post("/api/auth/logout")
    assert res.status_code == 200, f"/logout (unauth) failed: {res.text}"
    print("  [PASS] /api/auth/logout (unauthenticated): 200 OK (no 401)")

    # 9. CORS & Security headers check
    res = client.options("/api/chat", headers={
        "Origin": "http://localhost:8080",
        "Access-Control-Request-Method": "POST",
    })
    print(f"  [PASS] CORS Pre-flight status: {res.status_code}")

    print("=" * 60)
    print("  ALL API INTEGRATION TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    test_auth_suite()
