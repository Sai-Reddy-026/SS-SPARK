# 📖 SS SPARK — REST API Reference

The SS SPARK API provides RESTful endpoints for document upload, OCR ingestion, hybrid vector/keyword search, multi-turn chat sessions, authentication, and administrative controls.

- **Base URL (Local)**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

---

## 1. Authentication & Users (`/api/auth`, `/api/users`)

### `POST /api/auth/register`
Register a new user account with email and password.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "full_name": "Jane Doe"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "success": true,
    "data": {
      "user": { "id": "uuid", "email": "user@example.com", "full_name": "Jane Doe", "role": "user" },
      "tokens": { "access_token": "jwt...", "refresh_token": "random_token" }
    }
  }
  ```

### `POST /api/auth/login`
Authenticate with email and password.
- **Request Body**: `{"email": "user@example.com", "password": "SecurePassword123!"}`
- **Response `200 OK`**: Returns user profile and authentication tokens.

### `POST /api/auth/refresh`
Refresh expired access token.
- **Request Body**: `{"refresh_token": "..."}`
- **Response `200 OK`**: `{"data": {"access_token": "new_jwt..."}}`

### `GET /api/users/me`
Retrieve currently logged-in user profile.
- **Headers**: `Authorization: Bearer <access_token>`

---

## 2. Document Ingestion & Management (`/api/upload`, `/api/documents`)

### `POST /api/upload`
Upload and index one or more document files.
- **Content-Type**: `multipart/form-data`
- **Form Fields**: `files` (array of PDF, DOCX, PPTX, PNG, JPG, TXT)
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "doc_id",
        "filename": "sample_exam.pdf",
        "kind": "pdf",
        "size_mb": 1.24,
        "pages": 4,
        "chunks_indexed": 12,
        "paperqa_indexed": true,
        "uploaded_at": "2026-08-16T12:00:00Z"
      }
    ]
  }
  ```

### `GET /api/documents`
List all documents uploaded by the authenticated user.
- **Response `200 OK`**: `{"success": true, "data": [UploadedDoc, ...]}`

### `DELETE /api/documents/{doc_id}`
Delete a document, its disk file, its database record, and all vector store embeddings.

---

## 3. Hybrid RAG & Chat (`/api/chat`, `/api/sessions`)

### `POST /api/chat`
Send a question to the hybrid RAG / conversational AI pipeline.
- **Request Body**:
  ```json
  {
    "question": "What are the key recurring algorithms in Module 3?",
    "session_id": "optional-session-uuid"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "data": {
      "answer": "Based on the uploaded question papers, Dijkstra's algorithm and Prim's algorithm appear in 4 out of 5 exams...",
      "source": "exam_2024.pdf",
      "page": 3,
      "confidence": 0.94,
      "citations": [
        {
          "id": "cit_1",
          "source": "exam_2024.pdf",
          "page": 3,
          "snippet": "Q4. Write Dijkstra's algorithm for single-source shortest path...",
          "relevance": 0.92
        }
      ],
      "references": "1. exam_2024.pdf, Page 3",
      "session_id": "session-uuid",
      "cost": 0.00012,
      "status": "success"
    }
  }
  ```

### `GET /api/sessions`
List all chat sessions for the current user.

### `GET /api/sessions/{session_id}/history`
Retrieve message history for a specific chat session.

---

## 4. System & Health (`/health`, `/api/admin`)

### `GET /health`
Quick health-check endpoint for load balancers and container orchestrators.
- **Response `200 OK`**:
  ```json
  {
    "status": "ok",
    "documents_in_db": 10,
    "paperqa_indexed": 10
  }
  ```

### `GET /api/admin/stats`
*(Admin role required)* Returns system-wide telemetry, user counts, document storage, and active RAG status.
