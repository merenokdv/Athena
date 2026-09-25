# Архитектура Athena (RAG)

## Продукт

**Athena** — локальный ассистент поддержки принятия решений по базе знаний.

## Пайплайн

```
ваши заметки (.md/.txt + PDF→md)
        │
        ▼
   ingest / индексация
   (chunk → nomic-embed-text → Chroma)
        │
        ▼
   вопрос в UI Athena
        │
        ├─ hybrid retrieve (vector + filename boost)
        │
        ▼
   Qwen (Ollama) + system prompt
        │
        ▼
   ответ + имена источников
```

## Источник знаний

Задаётся через `ATHENA_KB=/path/to/notes` или папку `knowledge_base/` в репозитории.

| Берём | Пропускаем |
|-------|------------|
| `.md`, `.txt` | `.git`, `assets`, картинки, пустые |
| PDF через `scripts/pdf_to_md.py` | «сырые» PDF напрямую |

Проверка: `PYTHONPATH=. python scripts/check_index.py`

## После обновления заметок

```bash
export ATHENA_KB=/path/to/notes   # если своя база
PYTHONPATH=. python -m app.ingest
PYTHONPATH=. python scripts/check_index.py
```

## UI

FastAPI (`app/server.py`) + `web/` · http://127.0.0.1:7860
