#!/usr/bin/env python3
"""Добавить <KB>/_pdf_converted/*.md в уже существующий индекс (без полного rebuild)."""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBED_MODEL,
    KNOWLEDGE_DIRS,
    OLLAMA_BASE_URL,
)


def main() -> int:
    root = KNOWLEDGE_DIRS[0]
    src = root / "_pdf_converted"
    files = sorted(src.rglob("*.md"))
    print(f"KB={root} files={len(files)}")
    if not files:
        print("Нет _pdf_converted/*.md — сначала scripts/pdf_to_md.py")
        return 1

    docs = []
    for p in files:
        loaded = TextLoader(str(p), encoding="utf-8").load()
        for d in loaded:
            rel = str(p.relative_to(root))
            d.page_content = f"Заметка: {rel}\n\n{d.page_content}"
            d.metadata["source"] = str(p)
            d.metadata["filename"] = p.name
        docs.extend(loaded)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    print(f"chunks={len(chunks)}")

    emb = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    vs = Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=emb,
        collection_name=COLLECTION_NAME,
    )
    before = vs._collection.count()
    bs = 64
    for i in range(0, len(chunks), bs):
        batch = chunks[i : i + bs]
        print(f"embed {i + 1}-{i + len(batch)}/{len(chunks)}")
        vs.add_documents(batch)
    after = vs._collection.count()
    print(f"done before={before} after={after} added={after - before}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
