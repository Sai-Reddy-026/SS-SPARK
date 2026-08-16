"""
backend/tests/test_upload_pipeline.py
Test and trace the complete upload -> MongoDB -> Vector Store -> PaperQA -> List API pipeline
for PDF, Image, and TXT files.
"""

import asyncio
import io
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from main import app
from database.models import get_documents, get_document_by_id
from database.user_models import UserRecord, create_user, get_user_by_email
from core.security import create_access_token

client = TestClient(app)

def test_pipeline():
    print("=" * 60)
    print("STEP 1: REPRODUCE & TRACE UPLOAD PIPELINE")
    print("=" * 60)

    # 1. Authenticate a test user
    email = f"uploader_{os.urandom(4).hex()}@test.com"
    reg_res = client.post("/api/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": "Pipeline Tester"
    })
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
    token = reg_res.json()["data"]["access_token"]
    user_id = reg_res.json()["data"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"1. Authenticated user: {email} (id: {user_id})")

    # 2. Test PDF Upload
    print("\n--- Testing PDF Upload ---")
    pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Contents 4 0 R/Parent 2 0 R>>endobj\n4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (Hello Distributed Systems Exam 2024) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000214 00000 n\ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n308\n%%EOF"
    pdf_upload = client.post(
        "/api/upload",
        files={"files": ("exam_paper.pdf", pdf_content, "application/pdf")},
        headers=headers,
    )
    print(f"PDF Upload Status: {pdf_upload.status_code}")
    print(f"PDF Upload Response: {pdf_upload.json()}")
    assert pdf_upload.status_code == 200
    pdf_data = pdf_upload.json()["data"][0]
    pdf_doc_id = pdf_data["id"]

    # 3. Test TXT Upload
    print("\n--- Testing TXT Upload ---")
    txt_content = b"Question 1: Explain ACID properties in DBMS.\nQuestion 2: What is 2-Phase Locking protocol?"
    txt_upload = client.post(
        "/api/upload",
        files={"files": ("dbms_notes.txt", txt_content, "text/plain")},
        headers=headers,
    )
    print(f"TXT Upload Status: {txt_upload.status_code}")
    print(f"TXT Upload Response: {txt_upload.json()}")
    assert txt_upload.status_code == 200
    txt_data = txt_upload.json()["data"][0]
    txt_doc_id = txt_data["id"]

    # 4. Test Image Upload
    print("\n--- Testing Image Upload ---")
    # Minimal 1x1 PNG
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
    img_upload = client.post(
        "/api/upload",
        files={"files": ("paper_scan.png", png_content, "image/png")},
        headers=headers,
    )
    print(f"Image Upload Status: {img_upload.status_code}")
    print(f"Image Upload Response: {img_upload.json()}")
    assert img_upload.status_code == 200
    img_data = img_upload.json()["data"][0]
    img_doc_id = img_data["id"]

    # 5. Check Document List API (/api/documents)
    print("\n--- Checking GET /api/documents ---")
    list_res = client.get("/api/documents", headers=headers)
    print(f"List API Status: {list_res.status_code}")
    list_data = list_res.json()
    print(f"List API Response Data Count: {len(list_data.get('data', []))}")
    for d in list_data.get("data", []):
        print(f"  - Document ID: {d['id']}, Name: {d['name']}, Kind: {d['kind']}, Pages: {d['pages']}")

    returned_ids = [d["id"] for d in list_data.get("data", [])]
    assert pdf_doc_id in returned_ids, "PDF doc ID missing from GET /api/documents"
    assert txt_doc_id in returned_ids, "TXT doc ID missing from GET /api/documents"
    assert img_doc_id in returned_ids, "Image doc ID missing from GET /api/documents"

    # 6. Check unauthenticated / other user isolation
    print("\n--- Checking Multi-User Isolation on GET /api/documents ---")
    other_list = client.get("/api/documents") # no auth
    assert len(other_list.json().get("data", [])) == 0, "Unauthenticated list returned user documents!"
    print("  [PASS] Isolation verified: unauthenticated sees 0 docs.")

    print("\n" + "=" * 60)
    print("BACKEND PIPELINE VERIFICATION PASSED")
    print("=" * 60)

if __name__ == "__main__":
    test_pipeline()
