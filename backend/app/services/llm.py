from __future__ import annotations

import re
from typing import List, Optional, Tuple

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings

# Whole-document overview intents
OVERVIEW_PATTERNS = [
    r"\bsummar(y|ise|ize|isation|ization)\b.*\b(this|the)\s+(doc|document|file|notes?)\b",
    r"\bsummar(y|ise|ize|isation|ization)\b\s*(this|everything|all)?\s*$",
    r"\boverview\b",
    r"\bkey\s+points?\b",
    r"\bmain\s+points?\b",
    r"\btl;?dr\b",
    r"\bwhat\s+is\s+this\s+(doc|document|file)\s+about\b",
    r"\bexplain\s+(this|the)\s+(doc|document|file)\b",
    r"\boutline\b",
    r"\brecap\b",
    r"\bsummar(y|ise|ize).*\bin\s+detail\b",
    r"\bdetailed\s+summar",
]

# "summarize module 1" / "summarize section X" — section-scoped, not whole-doc dump
SECTION_SUMMARIZE_RE = re.compile(
    r"\bsummar(y|ise|ize|isation|ization)\b.{0,40}\b(module|chapter|section|unit|part)\b",
    re.IGNORECASE,
)


def is_overview_question(question: str) -> bool:
    q = question.lower().strip()
    if SECTION_SUMMARIZE_RE.search(q):
        return False
    return any(re.search(pat, q) for pat in OVERVIEW_PATTERNS)


def is_section_summarize_question(question: str) -> bool:
    return bool(SECTION_SUMMARIZE_RE.search(question.lower().strip()))


def _configure_genai() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    genai.configure(api_key=settings.gemini_api_key)


def _chat_model_candidates() -> List[str]:
    settings = get_settings()
    primary = settings.gemini_chat_model
    fallbacks = [
        primary,
        "gemini-flash-latest",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
    ]
    # Preserve order, unique
    seen = set()
    out: List[str] = []
    for m in fallbacks:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def get_chat_model(model_name: Optional[str] = None) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return ChatGoogleGenerativeAI(
        model=model_name or settings.gemini_chat_model,
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
3. ## Important details (dates, names, policies, numbers, definitions if present)
4. ## Notable sections (if the doc has clear parts)

Be accurate. Do not invent content that is not in the source.
When the user asks for a detailed summary, be thorough and cover each major subsection.
"""


def _content_to_str(content) -> str:
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content)


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "resource_exhausted" in message or "quota" in message


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


def extract_section_text(full_text: str, question: str) -> Optional[str]:
    """Best-effort slice for 'summarize module 1' style questions."""
    m = re.search(
        r"(module|chapter|section|unit|part)\s*([0-9]+|[ivxlcdm]+|[a-z])\b",
        question,
        re.IGNORECASE,
    )
    if not m or not full_text:
        return None
    kind, num = m.group(1), m.group(2)
    # Match headings like "MODULE 1", "Module 1 —", "1. MODULE 1"
    start_re = re.compile(
        rf"(?im)^(?:\s*\d+\.\s*)?{re.escape(kind)}\s*{re.escape(num)}\b[^\n]*$"
    )
    starts = list(start_re.finditer(full_text))
    if not starts:
        # Also try "MODULE 1 —" inline without requiring line start only
        start_re2 = re.compile(rf"(?i)\b{re.escape(kind)}\s*{re.escape(num)}\b\s*[—\-:]")
        starts = list(start_re2.finditer(full_text))
    if not starts:
        return None

    start = starts[0].start()
    # End at next same-level module/chapter heading with higher/different number
    next_re = re.compile(rf"(?im)^(?:\s*\d+\.\s*)?{re.escape(kind)}\s+[0-9ivxlcdm]+\b")
    end = len(full_text)
    for match in next_re.finditer(full_text, start + 1):
        # skip if it's the same heading we started on
        if match.start() <= start:
            continue
        end = match.start()
        break
    section = full_text[start:end].strip()
    return section if len(section) > 40 else None


async def _ainvoke(prompt: str) -> str:
    last_err: Optional[Exception] = None
    for model_name in _chat_model_candidates():
        try:
            llm = get_chat_model(model_name)
            result = await llm.ainvoke(prompt)
            return _content_to_str(result.content)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if _is_quota_error(exc) or "404" in str(exc) or "not found" in str(exc).lower():
                continue
            raise
    assert last_err is not None
    raise last_err


def _heuristic_structured_summary(question: str, text: str, filename: str) -> str:
    """Offline fallback: outline from headings + lead sentences — covers more than a 2k trim."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    headings = [
        ln
        for ln in lines
        if (
            re.match(r"^(#{1,6}\s+|[A-Z0-9][A-Z0-9 \-—:]{8,}$)", ln)
            or re.match(r"^(module|chapter|section|unit|part)\s+\d+", ln, re.I)
            or re.match(r"^\d+(\.\d+)*\s+\S+", ln)
        )
    ][:40]

    # Lead paragraphs: take first sentence-ish of each ~chunk of text
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 40]
    leads = []
    for p in paras[:25]:
        sent = re.split(r"(?<=[.!?])\s+", p)[0]
        if len(sent) > 30:
            leads.append(sent[:300])

    parts = [
        f"## Summary of {filename}",
        f"_Generated without Gemini chat (quota/unavailable). Structured extract for:_ **{question}**",
        "",
        "### Outline",
    ]
    if headings:
        parts.extend(f"- {h}" for h in headings)
    else:
        parts.append("- (No clear headings detected)")
    parts.extend(["", "### Key excerpts"])
    parts.extend(f"- {s}" for s in leads[:18])
    # Include a longer body so detail questions aren't empty
    body_limit = min(len(text), 12000)
    parts.extend(["", "### Source body (truncated if very long)", text[:body_limit]])
    if len(text) > body_limit:
        parts.append(f"\n_… {len(text) - body_limit} more characters not shown_")
    return "\n".join(parts)


def _extractive_fallback(question: str, contexts: List[dict], *, overview: bool = False) -> str:
    if not contexts:
        return "No document content available."
    # Prefer one combined text for heuristic summary
    if len(contexts) == 1 or overview:
        combined = "\n\n".join(c.get("content", "") for c in contexts)
        filename = contexts[0].get("filename", "document")
        return _heuristic_structured_summary(question, combined, filename)

    combined = "\n\n".join(
        f"### From {c.get('filename', 'document')}\n{c.get('content', '')}" for c in contexts[:30]
    )
    filename = contexts[0].get("filename", "document")
    return _heuristic_structured_summary(question, combined, filename)


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
        if _is_quota_error(exc):
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
                f"definitions, and policies. Use compact Markdown bullets.\n\n"
                f"Section content:\n{group_text}\n\n"
                f"Section summary:"
            )
            partials.append(await _ainvoke(map_prompt))

        reduce_prompt = (
            f"{SUMMARY_PROMPT}\n\n"
            f"User request: {question}\n\n"
            f"Below are section summaries covering the FULL document(s). "
            f"Merge them into one coherent detailed final answer. Do not drop important points "
            f"just because they appeared in only one section.\n\n"
            + "\n\n---\n\n".join(f"### Section {i}\n{p}" for i, p in enumerate(partials, start=1))
            + "\n\nFinal Markdown answer:"
        )
        return await _ainvoke(reduce_prompt)
    except Exception as exc:  # noqa: BLE001
        if _is_quota_error(exc):
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
        if overview:
            if len(contexts) > 6 and all(c.get("chunk_id") is not None for c in contexts):
                answer = await map_reduce_summarize(question, contexts)
            else:
                answer = await generate_answer(question, contexts, overview=True)
            step = 80
            for i in range(0, len(answer), step):
                yield answer[i : i + step]
            return

        # Try streaming with model fallbacks
        last_err: Optional[Exception] = None
        for model_name in _chat_model_candidates():
            try:
                llm = get_chat_model(model_name)
                prompt = build_prompt(question, contexts, overview=False)
                async for chunk in llm.astream(prompt):
                    content = chunk.content
                    if not content:
                        continue
                    yield _content_to_str(content)
                return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if _is_quota_error(exc) or "404" in str(exc) or "not found" in str(exc).lower():
                    continue
                raise
        if last_err and _is_quota_error(last_err):
            yield _extractive_fallback(question, contexts, overview=False)
            return
        if last_err:
            raise last_err
    except Exception as exc:  # noqa: BLE001
        if _is_quota_error(exc):
            yield _extractive_fallback(question, contexts, overview=overview)
            return
        raise
