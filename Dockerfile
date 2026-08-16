# ============================================================
# Dockerfile for SS SPARK Backend
# ============================================================
FROM python:3.12-slim

# Install system dependencies: Tesseract OCR, Poppler/MuPDF tools, build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    libmagic1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend requirements and install dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy PaperQA engine and backend source code
COPY paper-qa /app/paper-qa
COPY backend /app/backend

WORKDIR /app/backend

# Create uploads and chroma directories
RUN mkdir -p /app/backend/uploads /app/backend/chroma_db

# Expose FastAPI default port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run Uvicorn with dynamic platform PORT binding (0.0.0.0)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
