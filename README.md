# Athena

Локальный RAG-ассистент поддержки принятия решений: **Qwen (Ollama) + Chroma + минималистичный UI**.

Отвечает по вашей базе знаний (заметки, регламенты, FAQ) и указывает источники. Данные остаются на вашей машине.

## Требования

- Python 3.11+
- [Ollama](https://ollama.com/) с моделями:
  - LLM: `qwen3.5:27b` (или `qwen3.5:9b` для скорости)
  - Embeddings: `nomic-embed-text`
- Рекомендуется NVIDIA GPU (для 27B удобна карта ~24 ГБ VRAM)

```bash
ollama pull qwen3.5:27b
ollama pull nomic-embed-text
```

## Быстрый старт (демо-база из репозитория)

В репозитории есть пример `knowledge_base/` (учебные регламенты). Личные заметки **не входят** в git.

```bash
git clone git@github.com:merenokdv/Athena.git
cd Athena

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# индекс демо-документов
PYTHONPATH=. python -m app.ingest

# UI
bash scripts/run_ui.sh
# → http://127.0.0.1:7860
```

Проверка покрытия индекса:

```bash
PYTHONPATH=. python scripts/check_index.py
```

## Как подключить свою базу знаний (другие заметки)

### Способ 1 — переменная окружения (рекомендуется)

Укажите папку с `.md` / `.txt` (Obsidian vault, экспорт Notion, папка с регламентами и т.д.):

```bash
export ATHENA_KB="/absolute/path/to/your/notes"

# опционально: PDF → Markdown рядом с заметками
PYTHONPATH=. python scripts/pdf_to_md.py

# пересобрать индекс
PYTHONPATH=. python -m app.ingest
PYTHONPATH=. python scripts/check_index.py

# запуск UI (подхватит ту же ATHENA_KB через config при ingest;
# для UI достаточно уже построенного индекса)
bash scripts/run_ui.sh
```

Чтобы не экспортировать каждый раз:

```bash
# Linux/macOS
echo 'export ATHENA_KB="/absolute/path/to/your/notes"' >> ~/.bashrc
```

Или одноразово:

```bash
ATHENA_KB=~/Documents/MyVault bash scripts/run_ui.sh
```

> Важно: UI читает **уже собранный** индекс в `data/chroma/`.  
> После смены `ATHENA_KB` всегда заново запускайте `python -m app.ingest`.

### Способ 2 — положить файлы в `knowledge_base/`

```bash
rm -rf knowledge_base/*
cp -R /path/to/your/notes/*.md knowledge_base/
PYTHONPATH=. python -m app.ingest
bash scripts/run_ui.sh
```

### Способ 3 — правка `app/config.py`

Можно жёстко прописать путь в `KNOWLEDGE_DIRS` (удобно для одного постоянного vault).

## Что индексируется

| Берём | Пропускаем |
|-------|------------|
| `.md`, `.txt` | `.git`, `.obsidian`, `assets`, картинки, пустые файлы |
| PDF после `scripts/pdf_to_md.py` → `_pdf_converted/` | «сырые» PDF напрямую (часто шумят в поиске) |

## Когда обновили заметки

Индекс сам не обновляется:

```bash
export ATHENA_KB="/path/to/your/notes"   # если используете свою базу
PYTHONPATH=. python -m app.ingest
PYTHONPATH=. python scripts/check_index.py
```

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|------------|------------|--------------|
| `ATHENA_KB` | Путь к папке с заметками | `knowledge_base/` |
| `ATHENA_LLM` | Модель Ollama для ответов | `qwen3.5:27b` |
| `ATHENA_EMBED` | Embedding-модель | `nomic-embed-text` |
| `OLLAMA_HOST` | URL Ollama | `http://127.0.0.1:11434` |

Пример быстрого режима на слабой GPU:

```bash
export ATHENA_LLM=qwen3.5:9b
```

## Архитектура

```
ваши заметки  →  ingest (chunk + embed)  →  Chroma
                                              ↓
UI / API  →  hybrid retrieve  →  Qwen + prompt  →  ответ + источники
```

- **Ingest** — индексация документов  
- **Retrieve** — поиск (векторы + буст по имени файла)  
- **Generate** — ответ строго по найденному контексту  

Подробнее: `docs/ARCHITECTURE.md`, полный отчёт для защиты: `docs/REPORT.md`.

## API

- `GET /api/health` — статус и имя модели  
- `POST /api/ask` — `{"question":"..."}` → `{"answer","sources","model"}`

## Безопасность

- В git не попадают: личные заметки, `.venv`, векторный индекс `data/chroma/`.
- Не коммитьте свой vault и не указывайте в репозитории абсолютные пути к домашним папкам с секретами.
- UI по умолчанию слушает только `127.0.0.1` (без публичного share).

## Лицензия

Учебный / личный прототип. Модели — по лицензиям их авторов (Qwen, nomic-embed и т.д.).
