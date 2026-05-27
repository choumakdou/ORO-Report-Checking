"""pdf_parser.py — Extract text from PDF files using PyMuPDF."""
import os
from typing import Optional
import fitz  # PyMuPDF


def extract_text(pdf_path: str, max_pages: Optional[int] = None) -> str:
    """
    Extract all text from a PDF file.
    Returns concatenated text with page separators.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    try:
        doc = fitz.open(pdf_path)
        pages = []
        total = len(doc)
        limit = min(total, max_pages) if max_pages else total
        for i in range(limit):
            page = doc[i]
            text = page.get_text("text")
            pages.append(f"--- PAGE {i+1} ---\n{text}")
        doc.close()
        return "\n".join(pages)
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def extract_text_by_page(pdf_path: str) -> list:
    """Return list of (page_num, text) tuples."""
    if not pdf_path or not os.path.exists(pdf_path):
        return []
    try:
        doc = fitz.open(pdf_path)
        result = []
        for i in range(len(doc)):
            text = doc[i].get_text("text")
            result.append((i + 1, text))
        doc.close()
        return result
    except Exception:
        return []


def get_page_count(pdf_path: str) -> int:
    try:
        doc = fitz.open(pdf_path)
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0


def truncate_for_ai(text: str, max_chars: int = 90000) -> str:
    """Truncate text to fit within AI context window."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[... MIDDLE SECTION TRUNCATED ...]\n\n" + text[-half:]
