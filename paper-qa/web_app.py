import os
import shutil
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="PaperQA2 Web Interface", version="1.0.0")

# Setup directories
BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "uploaded_papers"
STATIC_DIR = BASE_DIR / "static"

UPLOAD_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Mount static directory
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class QueryRequest(BaseModel):
    query: str
    settings_name: Optional[str] = "default"
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None


class SettingsUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>PaperQA2 Web UI</h1><p>Frontend file missing.</p>")


@app.get("/api/documents")
async def list_documents():
    files = []
    for p in UPLOAD_DIR.glob("*"):
        if p.is_file():
            size_mb = round(p.stat().st_size / (1024 * 1024), 2)
            files.append({
                "name": p.name,
                "size_mb": size_mb,
                "path": str(p),
                "extension": p.suffix.lower()
            })
    return {"documents": files}


@app.post("/api/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    uploaded = []
    for file in files:
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded.append(file.filename)
    return {"message": f"Successfully uploaded {len(uploaded)} files.", "files": uploaded}


@app.delete("/api/documents/{filename}")
async def delete_document(filename: str):
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        return {"message": f"Deleted {filename}"}
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    return {"message": "Settings updated successfully."}


@app.get("/api/settings")
async def get_settings():
    return {
        "has_openai": bool(os.getenv("OPENAI_API_KEY")),
        "has_gemini": bool(os.getenv("GEMINI_API_KEY")),
        "has_anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


@app.post("/api/query")
async def ask_paperqa(req: QueryRequest):
    if req.openai_api_key:
        os.environ["OPENAI_API_KEY"] = req.openai_api_key
    if req.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key
    if req.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = req.anthropic_api_key

    # Check for API keys
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        raise HTTPException(
            status_code=400,
            detail="Please provide an API Key (OpenAI, Gemini, or Anthropic) in Settings before asking questions."
        )

    try:
        from paperqa import Docs, ask

        doc_paths = [str(p) for p in UPLOAD_DIR.glob("*") if p.is_file()]

        # Run in thread pool to prevent blocking event loop
        loop = asyncio.get_event_loop()

        def _run_pqa():
            docs = Docs()
            for dp in doc_paths:
                try:
                    docs.add(dp)
                except Exception as e:
                    print(f"Error adding document {dp}: {e}")

            if len(doc_paths) > 0:
                answer = docs.query(req.query)
                formatted_answer = str(answer)
                contexts = []
                if hasattr(answer, "contexts"):
                    for c in answer.contexts:
                        contexts.append({
                            "text": getattr(c, "text", str(c)),
                            "citation": getattr(c, "citation", ""),
                            "score": getattr(c, "score", 0),
                        })
                return {
                    "question": req.query,
                    "answer": formatted_answer,
                    "contexts": contexts,
                    "cost": getattr(answer, "cost", 0),
                    "has_answer": bool(answer)
                }
            else:
                answer = ask(query=req.query)
                return {
                    "question": req.query,
                    "answer": str(answer),
                    "contexts": [],
                    "cost": getattr(answer, "cost", 0),
                    "has_answer": bool(answer)
                }

        result = await loop.run_in_executor(None, _run_pqa)
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("Starting PaperQA2 Web Application on http://localhost:8000 ...")
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)
