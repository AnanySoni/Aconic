from __future__ import annotations

import re
from typing import List

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings

OVERVIEW_PATTERNS = [
    r"\bsummar(y|ise|ize|isation|ization)\b",
    r"\boverview\b",
    r"\bkey\s+points?\b",
    r"\bmain\s+points?\b",
    r"\btl;?dr\b",
    r"\bwhat\s+is\s+this\s+(doc|document|file)\s+about\b",
    r"\bexplain\s+(this|the)\s+(doc|document|file)\b",
    r"\boutline\b",
    r"\brecap\b",
]


def is_overview_question(question: str) -> bool:
    q = question.lower().strip()
    return any(re.search(pat, q) for pat in OVERVIEW_PATTERNS)


def _configure_genai() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    genai.configure(api_key=settings.gemini_api_key)


def get_chat_model() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
    )


def chunk_text(text: str) -> List[str]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    return [c.strip() for c in chunks if c.strip()]


def _embed_one(text: str) -> List[float]:
    settings = get_settings()
    _configure_genai()
    result = genai.embed_content(
        model=settings.gemini_embedding_model,
        content=text,
        output_dimensionality=settings.embedding_dimensions,
    )
    embedding = result.get("embedding")
    if embedding is None and hasattr(result, "embedding"):
        embedding = result.embedding
    if not embedding:
        raise RuntimeError("Empty embedding returned from Gemini")
    return list(embedding)


def embed_texts(texts: List[str]) -> List[List[float]]:
    return [_embed_one(t) for t in texts]


def embed_query(query: str) -> List[float]:
    return _embed_one(query)


SYSTEM_PROMPT = """You are a helpful assistant for a personal knowledge base.
Answer using ONLY the provided document context. Do not invent facts.
If the context is incomplete for the question, say what is missing.
Write clear Markdown:
- Use ## / ### headings when structuring longer answers
- Use bullet lists for key points
- Use **bold** for important terms
- Keep paragraphs short and readable
Cite document filenames when helpful.
"""

SUMMARY_PROMPT = """You are summarizing uploaded documents for a knowledge base.
Cover the FULL provided content — do not ignore sections.
Produce well-structured Markdown with:
1. A short overview paragraph
2. ## Key points (bullets)
3. ## Important details (dates, names, policies, numbers if present)
4. ## Notable sections (if the doc has clear parts)

Be accurate. Do not invent content that is not in the source.
"""


def _content_to_str(content) -> str:
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content)


def build_prompt(question: str, contexts: List[dict], *, overview: bool = False) -> str:
    if not contexts:
        context_block = "(No relevant document chunks were retrieved.)"
    else:
        parts = []
        for i, ctx in enumerate(contexts, start=1):
            parts.append(
                f"[{i}] Document: {ctx.get('filename', 'unknown')}\n{ctx.get('content', '')}"
            )
        context_block = "\n\n".join(parts)

    system = SUMMARY_PROMPT if overview else SYSTEM_PROMPT
    return (
        f"{system}\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )


async def _ainvoke(prompt: str) -> str:
    llm = get_chat_model()
    result = await llm.ainvoke(prompt)
    return _content_to_str(result.content)


def _extractive_fallback(question: str, contexts: List[dict], *, overview: bool = False) -> str:
    if overview:
        # Pull more text for overview fallback
        body = "\n\n".join(
            f"### From {c.get('filename', 'document')}\n{c.get('content', '')[:2000]}"
            for c in contexts[:20]
        )
        return (
            f"## Extractive overview\n\n"
            f"_Gemini generateContent quota was exceeded; showing source excerpts for:_ "
            f"**{question}**\n\n{body}"
        )
    snippets = "\n\n".join(
        f"### From {c.get('filename', 'document')}\n{c.get('content', '')[:1200]}"
        for c in contexts[:5]
    )
    return (
        f"## Extractive answer\n\n"
        f"_Gemini generateContent quota was exceeded; excerpts for:_ **{question}**\n\n{snippets}"
    )


async def generate_answer(question: str, contexts: List[dict], *, overview: bool = False) -> str:
    if not contexts:
        return (
            "I could not find relevant information in your uploaded documents "
            "for that question."
        )
    try:
        prompt = build_prompt(question, contexts, overview=overview)
        return await _ainvoke(prompt)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "429" in message or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
            return _extractive_fallback(question, contexts, overview=overview)
        raise


async def map_reduce_summarize(question: str, contexts: List[dict]) -> str:
    """Summarize every chunk, then merge — covers the whole document."""
    if not contexts:
        return "I could not find document content to summarize."

    settings = get_settings()
    batch = settings.map_reduce_batch_size

    try:
        partials: List[str] = []
        for i in range(0, len(contexts), batch):
            group = contexts[i : i + batch]
            group_text = "\n\n".join(
                f"[{j}] {c.get('filename', 'doc')}:\n{c.get('content', '')}"
                for j, c in enumerate(group, start=1)
            )
            map_prompt = (
                f"{SUMMARY_PROMPT}\n\n"
                f"Summarize this section of the document(s). Keep key facts, names, dates, "
                f"and policies. Use compact Markdown bullets.\n\n"
                f"Section content:\n{group_text}\n\n"
                f"Section summary:"
            )
            partials.append(await _ainvoke(map_prompt))

        reduce_prompt = (
            f"{SUMMARY_PROMPT}\n\n"
            f"User request: {question}\n\n"
            f"Below are section summaries covering the FULL document(s). "
            f"Merge them into one coherent final answer. Do not drop important points "
            f"just because they appeared in only one section.\n\n"
            + "\n\n---\n\n".join(f"### Section {i}\n{p}" for i, p in enumerate(partials, start=1))
            + "\n\nFinal Markdown answer:"
        )
        return await _ainvoke(reduce_prompt)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "429" in message or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
            return _extractive_fallback(question, contexts, overview=True)
        raise


async def stream_answer(question: str, contexts: List[dict], *, overview: bool = False):
    if not contexts:
        yield (
            "I could not find relevant information in your uploaded documents "
            "for that question."
        )
        return
    try:
        # Overview / map-reduce answers are generated in one shot then streamed as chunks
        if overview:
            if len(contexts) > 6:
                answer = await map_reduce_summarize(question, contexts)
            else:
                answer = await generate_answer(question, contexts, overview=True)
            # Yield in pieces so the UI still feels streaming
            step = 80
            for i in range(0, len(answer), step):
                yield answer[i : i + step]
            return

        llm = get_chat_model()
        prompt = build_prompt(question, contexts, overview=False)
        async for chunk in llm.astream(prompt):
            content = chunk.content
            if not content:
                continue
            yield _content_to_str(content)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "429" in message or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
            answer = _extractive_fallback(question, contexts, overview=overview)
            yield answer
            return
        raise
