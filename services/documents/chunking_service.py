"""
Splits extracted text into overlapping, roughly token-sized chunks that get
embedded and stored for vector search. Simple character-based splitting is
used to avoid an extra tokenizer dependency; it is close enough for chunk
sizing purposes.
"""

DEFAULT_CHUNK_SIZE_CHARS = 1200
DEFAULT_CHUNK_OVERLAP_CHARS = 200


def chunk_pages(
    pages: list[tuple[int | None, str]],
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[dict]:
    """
    Returns a list of {"content": str, "page_number": int|None} dicts,
    in document order, ready to be embedded.
    """
    chunks: list[dict] = []
    for page_number, text in pages:
        text = text.strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                chunks.append({"content": piece, "page_number": page_number})
            if end == len(text):
                break
            start = end - chunk_overlap
    return chunks
