#!/usr/bin/env python3
"""Сверка файлов базы знаний с векторным индексом (только пути/счётчики)."""

from __future__ import annotations

from pathlib import Path

import chromadb

from app.config import (
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBED_MODEL,
    INDEX_SUFFIXES,
    KNOWLEDGE_DIRS,
    MAX_FILE_BYTES,
    SKIP_DIR_NAMES,
)


def iter_candidates() -> tuple[list[Path], int, int]:
    files: list[Path] = []
    empty = big = 0
    for root in KNOWLEDGE_DIRS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            if p.suffix.lower() not in INDEX_SUFFIXES:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size == 0:
                empty += 1
                continue
            if size > MAX_FILE_BYTES:
                big += 1
                continue
            files.append(p.resolve())
    return files, empty, big


def main() -> int:
    disk_files, empty, big = iter_candidates()
    disk_set = {str(p) for p in disk_files}
    roots = KNOWLEDGE_DIRS

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception as exc:
        print(f"Индекс не найден ({exc}). Сначала: PYTHONPATH=. python -m app.ingest")
        return 2

    raw = col.get(include=["metadatas"])
    indexed = {
        str(Path(m["source"]).resolve())
        for m in raw["metadatas"]
        if m and m.get("source")
    }

    missing = sorted(disk_set - indexed)
    stale = sorted(indexed - disk_set)
    covered = len(disk_set & indexed)

    print("ingest = индексация документов в векторную БД (Chroma)")
    print(f"KB dirs: {[str(r) for r in roots]}")
    print(f"types: {sorted(INDEX_SUFFIXES)} | chunk={CHUNK_SIZE}/{CHUNK_OVERLAP} | embed={EMBED_MODEL}")
    print(f"files on disk: {len(disk_set)}")
    print(f"files in index: {len(indexed)}")
    print(f"chunks (vectors): {col.count()}")
    print(f"skipped empty: {empty} | skipped too big: {big}")
    print(f"missing from index: {len(missing)}")
    print(f"stale in index: {len(stale)}")
    pct = (covered / len(disk_set) * 100) if disk_set else 0
    print(f"coverage: {pct:.1f}% ({covered}/{len(disk_set)})")

    def rel(p: str) -> str:
        path = Path(p)
        for root in roots:
            try:
                return str(path.relative_to(root))
            except ValueError:
                continue
        return p

    for p in missing[:20]:
        print("  MISSING", rel(p))
    for p in stale[:20]:
        print("  STALE", rel(p))

    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
