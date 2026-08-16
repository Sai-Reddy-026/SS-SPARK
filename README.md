# ✨ SS SPARK — AI Question Paper Analyzer & Document Intelligence

<p align="center">
  <img src="public/favicon.svg" alt="SS SPARK Logo" width="80" height="80" />
</p>

<p align="center">
  <b>A full-stack, enterprise-grade AI workspace designed for analyzing previous question papers, notes, and textbooks with cited, document-grounded answers.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Frontend-React_19_+_Vite-61DAFB?style=flat-square&logo=react" alt="React" />
  <img src="https://img.shields.io/badge/Router-TanStack_Router-FF4154?style=flat-square&logo=tanstack" alt="TanStack Router" />
  <img src="https://img.shields.io/badge/Backend-FastAPI_0.138-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Database-MongoDB-47A248?style=flat-square&logo=mongodb" alt="MongoDB" />
  <img src="https://img.shields.io/badge/Vector_DB-Qdrant_|_ChromaDB-FF6B00?style=flat-square" alt="Vector DB" />
  <img src="https://img.shields.io/badge/RAG_Engine-PaperQA_+_LiteLLM-7C6FF7?style=flat-square" alt="RAG" />
  <img src="https://img.shields.io/badge/Python-3.11_|_3.12-3776AB?style=flat-square&logo=python" alt="Python" />
</p>

---

## 🚀 Key Features

- **Document Analysis & OCR**: Drag-and-drop support for PDF, DOCX, TXT, PPTX, and image formats (PNG, JPG, WEBP) with automatic Optical Character Recognition (OCR).
- **Hybrid RAG Pipeline**: Combines **PaperQA**'s agentic document synthesis, **Qdrant / ChromaDB** vector search, and direct LLM answering for general conversation.
- **Strictly Grounded Citations**: Every answer derived from your documents includes direct source references, page numbers, extracted snippets, and confidence percentages.
- **ChatGPT-Style UI**: Sleek dark mode, syntax-highlighted code blocks, streaming message effects, collapsible sidebars, and question topic breakdown charts.
- **Full Authentication & Multi-Turn Memory**: JWT bearer tokens, bcrypt password hashing with SHA-256 pre-hashing, multi-session organization, and conversation context memory.
- **Admin & Monitoring Dashboard**: User management, system health metrics, security audit logs, and AI rate limiting controls.

---

## 🏗️ Architecture

```text
ss-spark/
├── frontend (src/)          # React 19 + TypeScript + TanStack Router + TailwindCSS
│   ├── components/          # Reusable UI, analyzer components, admin panels
│   ├── routes/              # File-based routing (chat, auth, admin dashboard)
│   ├── lib/                 # Typed API client, AuthProvider, state helpers
│   └── styles.css           # Modern design tokens, gradients & glassmorphism
│
├── backend/                 # FastAPI Python Backend
│   ├── api/                 # Modular API routes (auth, upload, chat, sessions, admin)
│   ├── core/                # Configuration (pydantic-settings) & Security (JWT, bcrypt)
│   ├── database/            # MongoDB persistence (Motor async client, indexes)
│   ├── rag/                 # RAG engine (PaperQA connector, VectorStore, Embeddings)
│   ├── services/            # Document parsing, chunking, OCR, and email dispatch
│   └── main.py              # Application entry point & lifespan manager
│
├── public/                  # Static assets & brand icons
├── Dockerfile               # Multi-stage production container
├── docker-compose.yml       # Production/local stack (Backend + MongoDB + Qdrant)
├── vercel.json              # Vercel SPA deployment configuration
├── render.yaml              # Render web service deployment blueprint
└── README.md                # Project documentation
```

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, TanStack Router, TanStack Query, TailwindCSS |
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings |
| **Database** | MongoDB (Motor async driver) |
| **Vector Search** | Qdrant / ChromaDB |
| **RAG & AI** | PaperQA, LiteLLM (Gemini 2.0 Flash, OpenAI GPT-4o, Anthropic Claude) |
| **Document Processing** | PyMuPDF (fitz), python-docx, python-pptx, pytesseract, Pillow |
| **Authentication** | JWT (python-jose), bcrypt password hashing |

---

## ⚡ Quickstart (Local Development)

### 1. Prerequisites
- **Node.js** (v18+) & **npm**
- **Python** (3.11+)
- **MongoDB** (running locally on port `27017` or a MongoDB Atlas URI)

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your GEMINI_API_KEY, OPENAI_API_KEY, or other LLM keys

# Start FastAPI server (runs on http://localhost:8000)
python start.py
```

Swagger API documentation will be accessible at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend Setup
```bash
# From the project root
npm install

# Start Vite dev server (runs on http://localhost:8080)
npm run dev
```

Open your browser at: [http://localhost:8080](http://localhost:8080)

---

## 🐳 Docker Deployment

To spin up the entire containerized stack (**SS SPARK Backend + MongoDB + Qdrant**) with one command:

```bash
docker compose up -d --build
```

---

## 🌐 Production Deployment

Refer to the complete [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step instructions on deploying:
- **Frontend** → Vercel
- **Backend** → Render / Railway
- **Database** → MongoDB Atlas

---

## 📄 License
This project is licensed under the MIT License.
