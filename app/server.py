"""
Минималистичный UI (FastAPI + static).
Стиль: воздух, светлая палитра, тихая типографика — в духе product-UI Gleb Kuznetsov.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import LLM_MODEL, TOP_K
from app.rag_chain import RagAssistant

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_assistant: RagAssistant | None = None


def get_assistant() -> RagAssistant:
    global _assistant
    if _assistant is None:
        _assistant = RagAssistant()
    return _assistant


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    model: str


app = FastAPI(title="Athena", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "model": LLM_MODEL}


@app.post("/api/ask", response_model=AskResponse)
def ask(body: AskRequest):
    try:
        result = get_assistant().ask(body.question.strip(), k=TOP_K)
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail=f"Ошибка генерации (часто нехватка VRAM: 27B и embed по очереди). {exc}",
        ) from exc
    sources = [Path(s).name for s in result.sources]
    return AskResponse(answer=result.answer, sources=sources, model=LLM_MODEL)


def main() -> None:
    import os
    import uvicorn

    host = os.environ.get("ATHENA_HOST", "127.0.0.1")
    port = int(os.environ.get("ATHENA_PORT", "7860"))
    uvicorn.run(
        "app.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
