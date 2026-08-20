# ============================================================
# Dockerfile for SS SPARK Backend
# ============================================================
FROM python:3.12-slim

# Install system dependencies: Tesseract OCR (with English, OSD, Hindi, Telugu), Poppler/MuPDF tools, build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-osd \
    tesseract-ocr-hin \
    tesseract-ocr-tel \
    libmagic1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend requirements and install dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy and install internal PaperQA package
COPY packages/paperqa /app/packages/paperqa
RUN pip install --no-cache-dir -e /app/packages/paperqa

# Copy backend source code
COPY backend /app/backend

WORKDIR /app/backend

# Create uploads and chroma directories
RUN mkdir -p /app/backend/uploads /app/backend/chroma_db

# Expose FastAPI default port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run Uvicorn with dynamic platform PORT binding (0.0.0.0) and proxy headers for cloud reverse proxies
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
