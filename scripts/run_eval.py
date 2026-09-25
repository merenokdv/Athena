"""Прогон контрольных запросов (под демо knowledge_base/ или свою ATHENA_KB)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.rag_chain import RagAssistant

QUESTIONS = [
    "Как оформить заявку на доступ к VPN для нового сотрудника?",
    "Какой SLA у инцидентов приоритета P1?",
    "Что делать при утере корпоративного ноутбука?",
    "Какие документы нужны для командировки?",
    "Можно ли установить стороннее ПО без согласования?",
    "Какой пароль у сервера бухгалтерии?",  # вне базы — отказ
]


def main() -> None:
    assistant = RagAssistant()
    results = []
    for q in QUESTIONS:
        t0 = time.time()
        ans = assistant.ask(q)
        dt = round(time.time() - t0, 2)
        results.append(
            {
                "question": q,
                "answer": ans.answer,
                "sources": [Path(s).name for s in ans.sources],
                "seconds": dt,
            }
        )
        print("=" * 80)
        print(f"Q: {q}")
        print(f"t: {dt}s")
        print(f"sources: {[Path(s).name for s in ans.sources]}")
        print(ans.answer)
        print()

    out = Path(__file__).resolve().parent.parent / "docs" / "test_run_raw.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
