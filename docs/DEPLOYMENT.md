# 🚀 SS SPARK — Production Deployment Guide

This guide details how to deploy the full **SS SPARK** stack (**FastAPI Backend** + **React/TanStack Frontend** + **MongoDB Atlas** + **Qdrant Vector Store** + **OAuth & SMTP**).

---

## 📋 Architecture Topology

```text
User Browser
    │
    ▼
Vercel (SS SPARK React Frontend)
    │  [VITE_API_URL]
    ▼
Render / Docker / VPS (SS SPARK FastAPI Backend)
    ├── MongoDB Atlas (Users, Sessions, Messages, Document Metadata)
    ├── Qdrant Cloud / ChromaDB (Vector Embeddings & Chunks)
    └── LLM / RAG Engine (PaperQA + Gemini / OpenAI / Anthropic)
```

---

## 🌐 Deployment: Vercel (Frontend) + Render (Backend)

### Step 1: Database Setup (MongoDB Atlas)
1. Navigate to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) and create an M0 free tier cluster.
2. In **Security → Database Access**, create a user with `readWriteAnyDatabase` permissions.
3. In **Security → Network Access**, add `0.0.0.0/0` (allows connections from Render/Vercel).
4. Click **Connect → Drivers (Python 3.12+)** and copy your URI:
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/ss_spark?retryWrites=true&w=majority
   ```

### Step 2: Vector Database Setup (Qdrant Cloud)
1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io) and create a free 1GB cluster.
2. Copy your **Cluster URL** (e.g. `https://xyz-abc.qdrant.tech`) and **API Key**.
3. Set in your backend environment:
   ```env
   USE_QDRANT=true
   QDRANT_HOST=https://xyz-abc.qdrant.tech
   QDRANT_API_KEY=your-qdrant-api-key
   QDRANT_COLLECTION=ss_spark_chunks
   ```
   *(Alternatively, leave `USE_QDRANT=false` to use embedded ChromaDB).*

### Step 3: Backend Deployment (Render)
1. In [Render Dashboard](https://dashboard.render.com), click **New + → Web Service**.
2. Connect your GitHub repository: `https://github.com/Sai-Reddy-026/SS-SPARK.git`.
3. Set configuration:
   - **Runtime:** `Docker` (Render automatically uses `Dockerfile`)
   - **Branch:** `main`
   - **Auto-Deploy:** `Yes`
4. Add **Environment Variables**:
   | Variable | Value | Notes |
   | :--- | :--- | :--- |
   | `MONGO_URI` | `mongodb+srv://...` | MongoDB Atlas connection string |
   | `MONGO_DB_NAME` | `ss_spark` | Database name |
   | `JWT_SECRET_KEY` | *(Click Generate or paste 64-char hex)* | Token signing secret |
   | `FRONTEND_URL` | `https://your-app.vercel.app` | Production frontend URL |
   | `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini API Key |
   | `GOOGLE_API_KEY` | `AIzaSy...` | LiteLLM alias for Gemini |
   | `OPENAI_API_KEY` | `sk-...` | *(Optional) OpenAI API Key* |
   | `USE_QDRANT` | `true` (or `false`) | Set `false` for embedded ChromaDB |
5. Click **Create Web Service**. Copy your live URL (e.g. `https://ss-spark-api.onrender.com`).

### Step 4: Frontend Deployment (Vercel)
1. In [Vercel Dashboard](https://vercel.com/new), click **Add New → Project** and import `SS-SPARK`.
2. Configure **Build & Development Settings**:
   - **Framework Preset:** `Vite`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.output/public`
3. Add **Environment Variable**:
   - `VITE_API_URL` = `https://ss-spark-api.onrender.com`
4. Click **Deploy**.

---

## 🐳 Self-Hosted Deployment (Docker Compose)

For deployment on a VPS (DigitalOcean, AWS EC2, Hetzner, Linode):

```bash
# 1. Clone repository
git clone https://github.com/Sai-Reddy-026/SS-SPARK.git
cd SS-SPARK

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env and provide your API keys

# 3. Start containers
docker compose up -d --build

# 4. Check service health
docker compose ps
curl http://localhost:8000/health
```

---

## 🔒 Security Checklist for Production

- [x] **JWT Secret Strength**: Ensure `JWT_SECRET_KEY` is at least 32 characters (`openssl rand -hex 32`).
- [x] **CORS Whitelisting**: Verify `FRONTEND_URL` matches your deployed domain.
- [x] **Environment Secrets**: Never commit `.env` files to git.
- [x] **File Storage Permissions**: Ensure `uploads/` is writable by the application user.
