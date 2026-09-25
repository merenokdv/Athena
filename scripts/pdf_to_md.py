"""
Конвертация PDF из базы знаний → Markdown для чистого RAG-поиска.

Куда пишет: <KB>/_pdf_converted/<относительный_путь>.md

  ATHENA_KB=/path/to/notes PYTHONPATH=. python scripts/pdf_to_md.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf

from app.config import KNOWLEDGE_DIRS

ROOT_KB = KNOWLEDGE_DIRS[0]
OUT_DIR = ROOT_KB / "_pdf_converted"


def safe_rel(path: Path, root: Path) -> Path:
    rel = path.relative_to(root)
    parts = [re.sub(r"[^\w\-.\u0400-\u04FF ]+", "_", p) for p in rel.parts]
    return Path(*parts).with_suffix(".md")


def pdf_to_markdown(pdf_path: Path) -> str:
    doc = pymupdf.open(pdf_path)
    parts: list[str] = [
        f"# {pdf_path.stem}",
        "",
        f"> Источник PDF: `{pdf_path.name}`",
        f"> Страниц: {doc.page_count}",
        "",
    ]
    for i, page in enumerate(doc, start=1):
        text = (page.get_text("text") or "").strip()
        parts.append(f"## Страница {i}")
        parts.append("")
        if text:
            text = re.sub(r"[ \t]+\n", "\n", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            parts.append(text)
        else:
            parts.append("_На странице не удалось извлечь текст (возможно скан без OCR)._")
        parts.append("")
    doc.close()
    return "\n".join(parts).strip() + "\n"


def main() -> int:
    if not ROOT_KB.exists():
        print(f"Нет базы знаний: {ROOT_KB}", file=sys.stderr)
        print("Задайте ATHENA_KB=/path/to/notes", file=sys.stderr)
        return 1

    pdfs = sorted(
        p
        for p in ROOT_KB.rglob("*.pdf")
        if ".git" not in p.parts and "_pdf_converted" not in p.parts
    )
    print(f"KB: {ROOT_KB}")
    print(f"Найдено PDF: {len(pdfs)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    converted = skipped = emptyish = 0
    for pdf in pdfs:
        out = OUT_DIR / safe_rel(pdf, ROOT_KB)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.stat().st_mtime >= pdf.stat().st_mtime:
            print(f"SKIP (актуален): {pdf.name}")
            skipped += 1
            continue
        try:
            md = pdf_to_markdown(pdf)
            body_len = len(re.sub(r"\s+", "", md))
            out.write_text(md, encoding="utf-8")
            flag = "OK"
            if body_len < 200:
                flag = "WARN-мало текста"
                emptyish += 1
            print(f"{flag}: {pdf.name} → {out.relative_to(ROOT_KB)} ({body_len} chars)")
            converted += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {pdf}: {exc}", file=sys.stderr)

    print(f"Готово. converted={converted} skipped={skipped} low_text={emptyish}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
