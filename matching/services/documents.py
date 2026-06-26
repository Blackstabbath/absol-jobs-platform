from pathlib import Path

from docx import Document
from PyPDF2 import PdfReader


def extract_text(file_field):
    suffix = Path(file_field.name).suffix.lower()
    file_field.open("rb")
    try:
        if suffix == ".pdf":
            reader = PdfReader(file_field)
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if suffix == ".docx":
            document = Document(file_field)
            return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
        if suffix == ".txt":
            return file_field.read().decode("utf-8", errors="ignore").strip()
    finally:
        file_field.close()
    return ""
