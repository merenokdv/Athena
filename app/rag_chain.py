"""
ШАГИ 2–3 пайплайна RAG — RETRIEVE + GENERATE.

Retrieve: гибрид (vector + буст по имени файла/ключевым словам) → top-k.
Generate: system prompt + контекст + вопрос → Qwen (Ollama).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBED_MODEL,
    ENABLE_THINKING,
    KEEP_ALIVE,
    KNOWLEDGE_DIRS,
    LLM_MODEL,
    NUM_CTX,
    OLLAMA_BASE_URL,
    TEMPERATURE,
    TOP_K,
)
from app.prompts import SYSTEM_PROMPT, USER_TEMPLATE

_GREETING_RE = re.compile(
    r"^(привет|здравствуй(те)?|добрый\s+(день|вечер|утро)|hello|hi|hey)[!?.]*$",
    re.IGNORECASE | re.UNICODE,
)

# Вопросы про размер/статус индекса — отвечаем из метаданных, без RAG по тексту
_META_STATS_RE = re.compile(
    r"(сколько|какое\s+количество|число|размер|статистик|покрыти)."
    r"{0,60}(замет|документ|файл|чанк|вектор|индекс|баз[аеы]|knowledge|notes)",
    re.IGNORECASE | re.UNICODE | re.DOTALL,
)

_STOP = {
    "что",
    "как",
    "какие",
    "какой",
    "какая",
    "какое",
    "про",
    "для",
    "есть",
    "мне",
    "мои",
    "моих",
    "моя",
    "мой",
    "в",
    "на",
    "и",
    "или",
    "по",
    "из",
    "the",
    "a",
    "an",
    "list",
    "список",
    "заметках",
    "заметки",
    "заметка",
    "расскажи",
    "дай",
    "пожалуйста",
    "нужно",
    "хочу",
    "можно",
    "где",
    "кто",
    "это",
    "которые",
    "который",
    "посмотреть",
    "посмотри",
    "рекомендуй",
    "посоветуй",
}


@dataclass
class RagAnswer:
    answer: str
    sources: list[str]
    context_preview: str


def _keywords(question: str) -> list[str]:
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", question.lower())
    out: list[str] = []
    for w in words:
        if len(w) < 3 or w in _STOP:
            continue
        out.append(w)
    return out


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text.lower())


def _stem(token: str) -> str:
    """Грубая основа для RU/EN (фильм/фильмов/фильмы → фильм)."""
    t = token.lower()
    for suf in (
        "ами",
        "ями",
        "ов",
        "ев",
        "ей",
        "ом",
        "ем",
        "ах",
        "ях",
        "ы",
        "и",
        "а",
        "я",
        "у",
        "ю",
        "е",
        "о",
        "s",
        "es",
        "ing",
    ):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def _stems_match(a: str, b: str) -> bool:
    sa, sb = _stem(a), _stem(b)
    if not sa or not sb:
        return False
    if sa == sb:
        return True
    # близкие основы одной длины ±2, общий префикс ≥4
    if len(sa) >= 4 and len(sb) >= 4 and abs(len(sa) - len(sb)) <= 2:
        n = min(len(sa), len(sb))
        return sa[:n] == sb[:n] and n >= max(4, min(len(sa), len(sb)) - 1)
    return False


def _keyword_score(doc, keywords: list[str]) -> float:
    src = f"{doc.metadata.get('filename', '')} {doc.metadata.get('source', '')}"
    src_words = _tokens(src)
    body_words = _tokens(doc.page_content or "")
    score = 0.0
    for kw in keywords:
        if any(_stems_match(kw, w) for w in src_words):
            score += 10.0
        # в теле — реже, чтобы не забивать шумными совпадениями
        body_hits = sum(1 for w in body_words if _stems_match(kw, w))
        if body_hits:
            score += min(3.0, 0.4 * body_hits)
    return score


def _filename_keys_match(key: str, keywords: list[str]) -> bool:
    words = _tokens(key)
    return any(_stems_match(kw, w) for kw in keywords for w in words)


class RagAssistant:
    def __init__(self) -> None:
        self.embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
        self.vectorstore = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=self.embeddings,
            collection_name=COLLECTION_NAME,
        )
        self.llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=TEMPERATURE,
            num_ctx=NUM_CTX,
            keep_alive=KEEP_ALIVE,
            reasoning=ENABLE_THINKING,
        )
        # индекс имя_файла → ids (для буста без полного скана документов каждый раз)
        self._filename_index: dict[str, list[str]] = {}
        try:
            raw = self.vectorstore._collection.get(include=["metadatas"])
            for _id, meta in zip(raw["ids"], raw["metadatas"]):
                name = (meta or {}).get("filename") or ""
                src = (meta or {}).get("source") or ""
                key = f"{name} {src}".lower()
                self._filename_index.setdefault(key, []).append(_id)
        except Exception:
            self._filename_index = {}

    def _docs_by_filename_keywords(self, keywords: list[str], limit: int):
        from langchain_core.documents import Document

        scored: list[tuple[int, list[str]]] = []
        for key, id_list in self._filename_index.items():
            words = _tokens(key)
            hits = sum(1 for kw in keywords if any(_stems_match(kw, w) for w in words))
            if hits:
                scored.append((hits, id_list))
        scored.sort(key=lambda x: x[0], reverse=True)

        ids: list[str] = []
        for _hits, id_list in scored:
            ids.extend(id_list)
            if len(ids) >= limit * 4:
                break
        if not ids:
            return []
        ids = ids[: limit * 4]
        got = self.vectorstore._collection.get(ids=ids, include=["metadatas", "documents"])
        docs = []
        for meta, text in zip(got["metadatas"], got["documents"]):
            docs.append(Document(page_content=text or "", metadata=meta or {}))
        return docs

    def retrieve(self, question: str, k: int = TOP_K):
        """Гибридный retrieve: vector top-N → реранк по ключам/имени файла."""
        keywords = _keywords(question)
        pool = max(k * 5, 20)

        paired = self.vectorstore.similarity_search_with_relevance_scores(question, k=pool)

        if keywords:
            short_q = " ".join(keywords[:4])
            if short_q.strip().lower() != question.strip().lower():
                paired += self.vectorstore.similarity_search_with_relevance_scores(short_q, k=pool)

        seen: set[str] = set()
        candidates = []
        for doc, rel in paired:
            key = f"{doc.metadata.get('source','')}|{(doc.page_content or '')[:80]}"
            if key in seen:
                continue
            seen.add(key)
            vec = float(rel) if rel is not None else 0.0
            boost = _keyword_score(doc, keywords)
            candidates.append((doc, vec + boost))

        if keywords:
            for doc in self._docs_by_filename_keywords(keywords, k):
                key = f"{doc.metadata.get('source','')}|{(doc.page_content or '')[:80]}"
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((doc, 20.0 + _keyword_score(doc, keywords)))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [d for d, _ in candidates[:k]]

    def index_stats(self) -> dict:
        """Только метаданные индекса (пути/счётчики), без чтения текста заметок."""
        raw = self.vectorstore._collection.get(include=["metadatas"])
        sources: set[str] = set()
        for meta in raw.get("metadatas") or []:
            src = (meta or {}).get("source")
            if src:
                sources.add(str(src))
        return {
            "files": len(sources),
            "chunks": self.vectorstore._collection.count(),
            "kb": [str(p) for p in KNOWLEDGE_DIRS],
            "model": LLM_MODEL,
            "collection": COLLECTION_NAME,
        }

    def ask(self, question: str, k: int = TOP_K) -> RagAnswer:
        q = question.strip()
        if _GREETING_RE.match(q):
            return RagAnswer(
                answer=(
                    "Привет! Я Athena — персональный ассистент по вашей базе знаний (RAG + локальная Qwen). "
                    "Задайте вопрос по загруженным документам — отвечу по найденным источникам."
                ),
                sources=[],
                context_preview="",
            )

        if _META_STATS_RE.search(q):
            stats = self.index_stats()
            kb = ", ".join(stats["kb"]) if stats["kb"] else "—"
            return RagAnswer(
                answer=(
                    f"В индексе сейчас:\n"
                    f"• файлов (уникальных источников): **{stats['files']}**\n"
                    f"• чанков (фрагментов для поиска): **{stats['chunks']}**\n"
                    f"• коллекция: `{stats['collection']}`\n"
                    f"• модель ответов: `{stats['model']}`\n"
                    f"• база: `{kb}`\n\n"
                    "Это метаданные индекса, не «угадывание» по тексту заметок. "
                    "После обновления файлов пересоберите индекс: `python -m app.ingest`."
                ),
                sources=[],
                context_preview="",
            )

        docs = self.retrieve(q, k=k)
        if not docs:
            return RagAnswer(
                answer="В базе знаний нет релевантных фрагментов по этому запросу.",
                sources=[],
                context_preview="",
            )

        context_parts = []
        sources: list[str] = []
        for i, doc in enumerate(docs, start=1):
            src = doc.metadata.get("source", "unknown")
            sources.append(src)
            # в промпт — только имя файла, без полного пути
            label = Path(src).name
            context_parts.append(f"[{i}] Источник: {label}\n{doc.page_content}")

        context = "\n\n".join(context_parts)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(context=context, question=q),
            },
        ]
        response = self.llm.invoke(messages)
        answer = response.content if hasattr(response, "content") else str(response)
        uniq_sources = list(dict.fromkeys(sources))
        return RagAnswer(answer=answer, sources=uniq_sources, context_preview=context)
