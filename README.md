# ✨ SS SPARK — AI Question Paper Analyzer & Document Intelligence

<p align="center">
  <img src="public/favicon.svg" alt="SS SPARK Logo" width="80" height="80" />
</p>

<p align="center">
  <b>A full-stack, production-grade AI workspace designed for analyzing previous question papers, notes, and textbooks with cited, document-grounded answers.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Frontend-React_19_+_Vite-61DAFB?style=flat-square&logo=react" alt="React" />
  <img src="https://img.shields.io/badge/Router-TanStack_Router-FF4154?style=flat-square&logo=tanstack" alt="TanStack Router" />
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Database-MongoDB-47A248?style=flat-square&logo=mongodb" alt="MongoDB" />
  <img src="https://img.shields.io/badge/Vector_DB-Qdrant_|_ChromaDB-FF6B00?style=flat-square" alt="Vector DB" />
  <img src="https://img.shields.io/badge/RAG_Engine-PaperQA_+_LiteLLM-7C6FF7?style=flat-square" alt="RAG" />
  <img src="https://img.shields.io/badge/Python-3.11_|_3.12-3776AB?style=flat-square&logo=python" alt="Python" />
</p>

---

## 🚀 Key Features

- **Multi-Format Ingestion & OCR**: Native drag-and-drop parsing for PDF, DOCX, TXT, PPTX, and image formats (PNG, JPG, WEBP) with automatic Tesseract OCR text extraction.
- **Hybrid RAG Pipeline**: Intelligent query router uniting **PaperQA** agentic document synthesis, **Qdrant / ChromaDB** vector search, and direct conversational LLMs (Gemini, OpenAI, Claude).
- **Strictly Grounded Citations**: Answers derived from uploaded papers feature source references, page numbers, extracted snippets, and confidence scores.
- **Modern Academic UI**: Sleek dark mode, responsive drawer panels, syntax-highlighted code blocks, streaming message effects, and document analytics.
- **Security & Multi-Tenant Isolation**: JWT tokens, bcrypt with SHA-256 pre-hashing, multi-session management, and tenant-isolated vector filtering.
- **Admin Dashboard**: System telemetry, document storage tracking, user administration, and AI rate limiting controls.

---

## 🏗️ Repository Architecture

```text
SS-SPARK/
├── frontend/                # React 19 Frontend (TanStack Start / Vite)
│   ├── public/              # Static assets & brand icons
│   ├── src/
│   │   ├── components/      # UI components, analyzer panel, admin sidebar
│   │   ├── hooks/           # Custom React hooks
│   │   ├── lib/             # Typed API client, AuthProvider, state helpers
│   │   ├── routes/          # TanStack Start file-based routing
│   │   └── styles.css       # Design tokens & TailwindCSS v4 tokens
│   ├── package.json         # Frontend dependencies & npm scripts
│   ├── package-lock.json    # Deterministic npm lockfile
│   ├── tsconfig.json        # TypeScript configuration
│   └── vite.config.ts       # Vite & TanStack Start build configuration
│
├── backend/                 # FastAPI REST API & RAG Engine
│   ├── api/                 # Endpoints (auth, upload, chat, documents, admin, sessions)
│   ├── core/                # Configuration (pydantic-settings), Security & CORS
│   ├── database/            # MongoDB models, indexes, and persistence layer
│   ├── schemas/             # Pydantic request/response validation schemas
│   ├── rag/                 # RAG engine (embeddings, Qdrant/ChromaDB store, PaperQA)
│   ├── services/            # Document chunking, OCR, chat orchestration
│   ├── tests/               # Automated test suite (test_e2e.py)
│   ├── uploads/             # Local upload storage (.gitkeep)
│   ├── main.py              # Application entry point & lifespan manager
│   ├── requirements.txt     # Python backend dependencies
│   └── start.py             # Pre-flight dev runner
│
├── packages/                # Internal Reusable Packages
│   └── paperqa/             # Clean PaperQA Core Engine Package
│       ├── paperqa/         # Core Python package source
│       └── pyproject.toml   # Standard package build definition
│
├── docs/                    # Production Technical Documentation
│   ├── ARCHITECTURE.md      # Architecture diagrams, RAG pipeline & sequence flows
│   ├── DEPLOYMENT.md        # Step-by-step Vercel, Render, Atlas & Qdrant setup
│   └── API_REFERENCE.md     # Complete REST API endpoint reference
│
├── .env.example             # Environment template
├── docker-compose.yml       # Production/local stack (Backend + MongoDB + Qdrant)
├── Dockerfile               # Production multi-stage Docker build for backend
├── render.yaml              # Render Blueprints Infrastructure-as-Code
└── vercel.json              # Vercel deployment configuration
```

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, TanStack Router, TanStack Query, TailwindCSS v4 |
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings |
| **Database** | MongoDB (Motor async driver) |
| **Vector Search** | Qdrant Cloud / ChromaDB |
| **RAG & AI** | PaperQA, LiteLLM (Gemini 2.0 Flash, OpenAI GPT-4o, Anthropic Claude) |
| **Document Processing** | PyMuPDF (fitz), python-docx, python-pptx, pytesseract, Pillow |
| **Authentication** | JWT (python-jose), bcrypt password hashing |

---

## ⚡ Quickstart (Local Development)

### 1. Prerequisites
- **Node.js** (v18+) & **npm**
- **Python** (3.11+)
- **MongoDB** (running locally on port `27017` or MongoDB Atlas URI)

### 2. Backend Setup
```bash
# Navigate to backend
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Open .env and set your GEMINI_API_KEY, OPENAI_API_KEY, or other LLM keys

# Start backend server (runs on http://localhost:8000)
python start.py
```

- Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- API Health Check: [http://localhost:8000/health](http://localhost:8000/health)

### 3. Frontend Setup
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start Vite dev server (runs on http://localhost:8080)
npm run dev
```

Open browser at: [http://localhost:8080](http://localhost:8080)

---

## 🐳 Docker Deployment

To spin up the entire containerized stack (**SS SPARK Backend + MongoDB + Qdrant**) with one command:

```bash
docker compose up -d --build
```

---

## 🌐 Production Deployment

Refer to the complete [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for step-by-step guides on deploying:
- **Frontend** → Vercel
- **Backend** → Render / Railway / Docker
- **Database** → MongoDB Atlas
- **Vector Store** → Qdrant Cloud

---

## 📚 Documentation Links

- [System Architecture & Pipelines](docs/ARCHITECTURE.md)
- [Production Deployment Guide](docs/DEPLOYMENT.md)
- [REST API Reference](docs/API_REFERENCE.md)

---

## 📄 License
This project is licensed under the MIT License.
