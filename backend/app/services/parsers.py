from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


def extract_text(path: str) -> str:
    file_path = Path(path)
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".docx":
        return _extract_docx(file_path)
    if ext == ".txt":
        return _extract_txt(file_path)
    raise ValueError(f"Unsupported file extension: {ext}")


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts).strip()


def _extract_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n\n".join(parts).strip()


def _extract_txt(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore").strip()
