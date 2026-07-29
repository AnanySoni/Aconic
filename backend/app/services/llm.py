from typing import List

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings


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
Answer the user's question using ONLY the provided document context.
If the context does not contain enough information, say you cannot find that in the uploaded documents.
Be concise and accurate. Prefer bullet points for lists when helpful.
Cite which document filename informed your answer when relevant.
"""


def build_prompt(question: str, contexts: List[dict]) -> str:
    if not contexts:
        context_block = "(No relevant document chunks were retrieved.)"
    else:
        parts = []
        for i, ctx in enumerate(contexts, start=1):
            parts.append(
                f"[{i}] Document: {ctx.get('filename', 'unknown')}\n{ctx.get('content', '')}"
            )
        context_block = "\n\n".join(parts)

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )


async def generate_answer(question: str, contexts: List[dict]) -> str:
    if not contexts:
        return (
            "I could not find relevant information in your uploaded documents "
            "for that question."
        )
    try:
        llm = get_chat_model()
        prompt = build_prompt(question, contexts)
        result = await llm.ainvoke(prompt)
        content = result.content
        if isinstance(content, list):
            return "".join(str(part) for part in content)
        return str(content)
    except Exception as exc:  # noqa: BLE001
        # Fallback for quota/billing issues so demos still return grounded answers
        message = str(exc)
        if "429" in message or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
            snippets = "\n\n".join(
                f"From {c.get('filename', 'document')}:\n{c.get('content', '')[:800]}"
                for c in contexts[:3]
            )
            return (
                "Gemini generateContent quota was exceeded, so here is an extractive "
                f"answer from your documents for: “{question}”\n\n{snippets}"
            )
        raise


async def stream_answer(question: str, contexts: List[dict]):
    if not contexts:
        yield (
            "I could not find relevant information in your uploaded documents "
            "for that question."
        )
        return
    try:
        llm = get_chat_model()
        prompt = build_prompt(question, contexts)
        async for chunk in llm.astream(prompt):
            content = chunk.content
            if not content:
                continue
            if isinstance(content, list):
                yield "".join(str(part) for part in content)
            else:
                yield str(content)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "429" in message or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
            answer = await generate_answer(question, contexts)
            yield answer
            return
        raise
