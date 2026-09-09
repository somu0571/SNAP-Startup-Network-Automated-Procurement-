"""
Document parser.
Handles PDF (via PyMuPDF) and DOCX (via python-docx) → plain text.
Strips headers/footers/page numbers where possible.
"""
import os
import re
try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    import fitz
from docx import Document


def parse_document(file_path: str) -> str:
    """
    Parse a PDF, DOCX, or TXT file and return clean plain text.
    Raises ValueError for unsupported formats.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        try:
            return _parse_docx(file_path)
        except Exception:
            # Fallback to UTF-8 text decoding if docx container parsing fails
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                raise ValueError(f"Could not parse docx file: {file_path}")
    elif ext in (".txt", ".text", ".md"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if content.strip():
                    return content
        except Exception:
            pass
        raise ValueError(f"Unsupported file format: {ext}. Use PDF, DOCX, or TXT.")


def _parse_pdf(file_path: str) -> str:
    """Extract text from PDF using PyMuPDF."""
    doc = fitz.open(file_path)
    pages = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        # Clean up common artifacts
        text = _clean_page_text(text, page_num + 1)
        if text.strip():
            pages.append(text.strip())

    doc.close()
    return "\n\n".join(pages)


def _parse_docx(file_path: str) -> str:
    """Extract text from DOCX using python-docx."""
    doc = Document(file_path)
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)

    return "\n\n".join(paragraphs)


def _clean_page_text(text: str, page_num: int) -> str:
    """Remove common headers, footers, and page numbers."""
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()
        # Skip standalone page numbers
        if re.match(r"^\d{1,3}$", stripped):
            continue
        # Skip common header/footer patterns
        if re.match(r"^(Page\s+\d+|Confidential|Draft|©)", stripped, re.IGNORECASE):
            continue
        cleaned.append(line)

    return "\n".join(cleaned)


def get_doc_metadata(file_path: str) -> dict:
    """Extract basic metadata from a document."""
    ext = os.path.splitext(file_path)[1].lower()
    file_size = os.path.getsize(file_path)

    metadata = {
        "filename": os.path.basename(file_path),
        "format": ext,
        "size_bytes": file_size,
    }

    if ext == ".pdf":
        try:
            doc = fitz.open(file_path)
            metadata["page_count"] = len(doc)
            doc.close()
        except Exception:
            metadata["page_count"] = 0

    return metadata
