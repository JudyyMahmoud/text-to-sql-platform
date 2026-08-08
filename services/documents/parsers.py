"""
File-type-specific text extraction. Each parser returns a list of
(page_number_or_None, text) tuples so the chunker can preserve page
references for citations.
"""
import csv
import io

import pandas as pd
from docx import Document as DocxDocument
from pypdf import PdfReader


def parse_pdf(file_path: str) -> list[tuple[int | None, str]]:
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i, text))
    return pages


def parse_docx(file_path: str) -> list[tuple[int | None, str]]:
    doc = DocxDocument(file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(None, full_text)] if full_text.strip() else []


def parse_txt(file_path: str) -> list[tuple[int | None, str]]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return [(None, content)] if content.strip() else []


def parse_csv(file_path: str) -> list[tuple[int | None, str]]:
    rows = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(", ".join(row))
    text = "\n".join(rows)
    return [(None, text)] if text.strip() else []


def parse_excel(file_path: str) -> list[tuple[int | None, str]]:
    sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
    pages = []
    for i, (sheet_name, df) in enumerate(sheets.items(), start=1):
        df = df.fillna("")
        text_lines = [f"Sheet: {sheet_name}", ", ".join(df.columns.astype(str))]
        for _, row in df.iterrows():
            text_lines.append(", ".join(str(v) for v in row.values))
        text = "\n".join(text_lines)
        if text.strip():
            pages.append((i, text))
    return pages


PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".doc": parse_docx,
    ".txt": parse_txt,
    ".md": parse_txt,
    ".csv": parse_csv,
    ".xlsx": parse_excel,
    ".xls": parse_excel,
}


def parse_file(file_path: str, extension: str) -> list[tuple[int | None, str]]:
    parser = PARSERS.get(extension.lower())
    if parser is None:
        raise ValueError(f"Unsupported file extension: {extension}")
    return parser(file_path)
