"""
Конфигурация Athena (локальный RAG-ассистент).

База знаний задаётся так (приоритет сверху вниз):
  1) переменная окружения ATHENA_KB=/path/to/your/notes
  2) иначе — встроенная демо-папка knowledge_base/
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_KB_DIR = PROJECT_ROOT / "knowledge_base"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "athena_kb"

# --- Источник знаний ---
_kb_env = os.environ.get("ATHENA_KB", "").strip()
if _kb_env:
    KNOWLEDGE_DIRS = [Path(_kb_env).expanduser().resolve()]
else:
    KNOWLEDGE_DIRS = [DEMO_KB_DIR]

# Что индексируем / что пропускаем
INDEX_SUFFIXES = {".md", ".txt"}
SKIP_DIR_NAMES = {
    ".git",
    ".obsidian",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "assets",
}
MAX_FILE_BYTES = 8 * 1024 * 1024

# --- Ollama ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
# По умолчанию 9b (быстрее, меньше VRAM). Качество: ATHENA_LLM=qwen3.5:27b
LLM_MODEL = os.environ.get("ATHENA_LLM", "qwen3.5:9b")
EMBED_MODEL = os.environ.get("ATHENA_EMBED", "nomic-embed-text")

# --- Чанкинг ---
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# --- Retrieval ---
TOP_K = 8

# --- Генерация ---
TEMPERATURE = 0.2
NUM_CTX = 4096
ENABLE_THINKING = False
KEEP_ALIVE = "30m"
