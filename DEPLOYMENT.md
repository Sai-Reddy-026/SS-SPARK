# 🚀 SS SPARK — Production Deployment Guide

This guide details how to deploy the full **SS SPARK** full-stack application (**FastAPI Backend** + **React/TanStack Frontend** + **MongoDB Atlas** + **Qdrant / ChromaDB Vector Store** + **Google/GitHub OAuth**).

---

## 📋 Architecture Overview

```text
User Browser
    │
    ▼
Vercel (SS SPARK React Frontend)
    │  [VITE_API_URL]
    ▼
Render / Railway / VPS (SS SPARK FastAPI Backend)
    ├── MongoDB Atlas (Users, Chat History, Document Metadata)
    ├── Qdrant Cloud / ChromaDB (Vector Embeddings & Chunks)
    └── LLM / RAG Engine (PaperQA + Gemini / OpenAI / Anthropic)
```

---

## 🌐 Deployment Option 1: Vercel (Frontend) + Render (Backend)
*(Recommended — Free Tier friendly, separate scaling)*

### Step 1: Deploy Database (MongoDB Atlas)
1. Navigate to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) and create a free M0 cluster.
2. Under **Security → Database Access**, create a user with read/write permissions.
3. Under **Security → Network Access**, add `0.0.0.0/0` (allow access from cloud providers).
4. Click **Connect → Drivers (Python)** and copy your connection string:
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/ss_spark?retryWrites=true&w=majority
   ```

### Step 2: Deploy Backend to Render
1. Push your repository to GitHub:
   ```bash
   git add .
   git commit -m "Prepare SS SPARK for production deployment"
   git push origin main
   ```
2. In [Render Dashboard](https://dashboard.render.com), click **New + → Web Service**.
3. Connect your GitHub repository.
4. Settings:
   - **Environment:** `Docker` (Render automatically uses the `Dockerfile`)
   - OR **Python 3.12:**
     - **Build Command:** `pip install -r backend/requirements.txt`
     - **Start Command:** `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2`
5. Configure **Environment Variables** in Render:
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/ss_spark?retryWrites=true&w=majority
   MONGO_DB_NAME=ss_spark
   JWT_SECRET_KEY=generate-a-64-character-random-secret-key-here
   FRONTEND_URL=https://your-frontend.vercel.app
   GEMINI_API_KEY=your-gemini-api-key
   GOOGLE_API_KEY=your-gemini-api-key
   OPENAI_API_KEY=your-openai-api-key
   USE_QDRANT=false
   ```
6. Copy your live API URL (e.g., `https://ss-spark-api.onrender.com`).

### Step 3: Deploy Frontend to Vercel
1. In [Vercel Dashboard](https://vercel.com/new), import your GitHub repository.
2. Configure **Build & Output Settings**:
   - **Framework Preset:** Vite
   - **Build Command:** `npm run build`
   - **Output Directory:** `.output/public`
3. Add **Environment Variable**:
   ```env
   VITE_API_URL=https://ss-spark-api.onrender.com
   ```
4. Click **Deploy**.

---

## 🐳 Deployment Option 2: VPS Server with Docker Compose
*(DigitalOcean Droplet, AWS EC2, Hetzner, Linode)*

```bash
# 1. Clone repository on your server
git clone https://github.com/your-username/ss-spark.git
cd ss-spark

# 2. Configure environment
cp backend/.env.example backend/.env
nano backend/.env  # Populate your production API keys

# 3. Launch with Docker Compose
docker compose up -d --build

# 4. Verify status
docker compose ps
curl http://localhost:8000/health
```

---

## 🔒 Security Best Practices for Production
1. **Rotate JWT Secret**: Use `openssl rand -hex 32` to generate a strong random secret key.
2. **Configure CORS**: Ensure `FRONTEND_URL` in the backend environment matches your production frontend URL.
3. **Database Credentials**: Never commit `.env` files into source control. Always inject them via cloud provider dashboards.
