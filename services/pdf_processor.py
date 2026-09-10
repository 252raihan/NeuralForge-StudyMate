"""
PDF processing module for NeuralForge StudyMate.
Extracts text from uploaded PDF files using pypdf.
"""

from pathlib import Path
from pypdf import PdfReader


def extract_text_from_pdf(file_path: str | Path) -> dict:
    """
    Extracts text content and basic page metadata from a PDF file.

    :param file_path: Path to the target PDF file.
    :return: Dictionary containing extraction results:
             {
                 "text": str,
                 "page_count": int,
                 "pages": list[dict]
             }
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    reader = PdfReader(str(path_obj))
    total_pages = len(reader.pages)
    page_items = []
    combined_chunks = []

    for idx, page in enumerate(reader.pages, start=1):
        extracted_page_text = page.extract_text() or ""
        clean_page_text = extracted_page_text.strip()
        page_items.append({
            "page_number": idx,
            "text": clean_page_text,
            "char_count": len(clean_page_text)
        })
        if clean_page_text:
            combined_chunks.append(clean_page_text)

    full_text = "\n\n".join(combined_chunks)

    return {
        "text": full_text,
        "page_count": total_pages,
        "char_count": len(full_text),
        "pages": page_items
    }
