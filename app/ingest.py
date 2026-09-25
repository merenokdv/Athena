"""
ШАГ 1 пайплайна RAG — INGEST (загрузка знаний).

  документы → текст → чанки → embeddings → Chroma

Запуск:
  PYTHONPATH=. python -m app.ingest

Своя база:
  ATHENA_KB=/path/to/notes PYTHONPATH=. python -m app.ingest
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

from app.config import (
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBED_MODEL,
    INDEX_SUFFIXES,
    KNOWLEDGE_DIRS,
    MAX_FILE_BYTES,
    OLLAMA_BASE_URL,
    SKIP_DIR_NAMES,
)


def _should_skip_dir(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def iter_source_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            print(f"WARN: папка не найдена, пропускаю: {root}")
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if _should_skip_dir(path):
                continue
            if path.suffix.lower() not in INDEX_SUFFIXES:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size == 0 or size > MAX_FILE_BYTES:
                continue
            files.append(path)
    return sorted(files)


def load_documents(roots: list[Path]) -> list[Document]:
    docs: list[Document] = []
    files = iter_source_files(roots)
    print(f"      Кандидатов файлов: {len(files)}")

    root0 = roots[0] if roots else None
    for path in files:
        suffix = path.suffix.lower()
        try:
            if suffix in {".md", ".txt"}:
                loaded = TextLoader(str(path), encoding="utf-8").load()
            elif suffix == ".pdf":
                loaded = PyPDFLoader(str(path)).load()
            else:
                continue
            for doc in loaded:
                if root0 and path.is_relative_to(root0):
                    rel = str(path.relative_to(root0))
                else:
                    rel = path.name
                doc.page_content = f"Заметка: {rel}\n\n{doc.page_content}"
                doc.metadata["source"] = str(path)
                doc.metadata["filename"] = path.name
            docs.extend(loaded)
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {path.name}: {exc}")
    return docs


def build_index() -> int:
    print(f"[1/4] Загрузка документов из: {[str(p) for p in KNOWLEDGE_DIRS]}")
    documents = load_documents(KNOWLEDGE_DIRS)
    if not documents:
        raise RuntimeError(
            "Не найдено документов (.md/.txt). "
            "Укажите ATHENA_KB=/path/to/notes или положите файлы в knowledge_base/"
        )
    print(f"      Загружено документов/страниц: {len(documents)}")

    print(f"[2/4] Нарезка на чанки (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"      Получено чанков: {len(chunks)}")

    print(f"[3/4] Embeddings через Ollama ({EMBED_MODEL})")
    embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)

    print(f"[4/4] Запись в Chroma → {CHROMA_DIR}")
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    batch_size = 64
    vectorstore = None
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        print(f"      embed {i + 1}–{i + len(batch)} / {len(chunks)}")
        if vectorstore is None:
            vectorstore = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                persist_directory=str(CHROMA_DIR),
                collection_name=COLLECTION_NAME,
            )
        else:
            vectorstore.add_documents(batch)

    assert vectorstore is not None
    count = vectorstore._collection.count()
    print(f"Готово. Векторов в коллекции: {count}")
    return count


def main() -> int:
    try:
        build_index()
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка ingest: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
