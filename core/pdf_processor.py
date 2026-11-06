"""
pdf_processor.py — Document text extraction (PDF, DOCX, TXT, MD, CSV, etc.)
Extracts clean, structured text from uploaded documents.
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional
import pypdf


def clean_text(text: str) -> str:
    """Normalize whitespace and clean up hyphenated line breaks."""
    if not text:
        return ""
    # Join hyphenated words split across lines
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
    # Replace multiple spaces/tabs with single space
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a PDF file page by page using pypdf."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)

    if total_pages == 0:
        raise ValueError("The uploaded PDF document contains no pages.")

    extracted_pages = []
    for idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                cleaned = clean_text(page_text)
                extracted_pages.append(f"--- Page {idx + 1} ---\n{cleaned}")
        except Exception as e:
            print(f"[Warning] Failed to extract text from page {idx + 1}: {e}")

    full_text = "\n\n".join(extracted_pages).strip()

    if not full_text:
        raise ValueError(
            "Could not extract any readable text from this PDF. "
            "It may be a scanned image or protected document without a text layer."
        )

    print(f"[Document Extractor] Extracted {len(full_text)} characters from {total_pages} PDF pages.")
    return full_text


def extract_text_from_docx(docx_path: str) -> str:
    """Extracts text from a Word DOCX file using built-in zipfile & XML parser."""
    try:
        with zipfile.ZipFile(docx_path) as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        # Extract text nodes
        paragraphs = []
        for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            p_text = "".join(node.text for node in p.iter() if node.tag.endswith("}t") and node.text)
            if p_text.strip():
                paragraphs.append(p_text.strip())
        full_text = "\n\n".join(paragraphs).strip()
        print(f"[Document Extractor] Extracted {len(full_text)} characters from DOCX.")
        return full_text
    except Exception as e:
        raise ValueError(f"Failed to read DOCX file: {e}")


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text based on file extension.
    Supports .pdf, .docx, .txt, .md, .csv, .json, .log, .rtf.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)

    elif ext == ".docx":
        return extract_text_from_docx(file_path)

    elif ext in (".txt", ".md", ".csv", ".json", ".log", ".rtf", ".text"):
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                cleaned = clean_text(content)
                if cleaned:
                    print(f"[Document Extractor] Read {len(cleaned)} characters from {ext} file.")
                    return cleaned
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Unable to decode text file: {os.path.basename(file_path)}")

    else:
        raise ValueError(
            f"Unsupported document format '{ext}'."
        )
