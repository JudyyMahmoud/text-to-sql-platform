"""
Embeddings run locally via fastembed (ONNX runtime), not through the LLM
provider. This is deliberate: not every LLM provider offers an embeddings
API (Groq, for example, only does chat/completions), so document search
would break if embeddings depended on the same provider as chat.

The model downloads automatically (~130MB) the first time it's used and is
cached in the container/volume afterward. It runs on CPU and needs no API
key at all.
"""
import asyncio
from functools import lru_cache

from fastembed import TextEmbedding

from app.config import settings


@lru_cache(maxsize=1)
def _get_model() -> TextEmbedding:
    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def _embed_sync(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return [vector.tolist() for vector in model.embed(texts)]


async def embed_chunks(chunk_texts: list[str]) -> list[list[float]]:
    """Embeds a batch of chunk texts. Runs in a thread since fastembed is CPU-bound/sync."""
    if not chunk_texts:
        return []
    return await asyncio.to_thread(_embed_sync, chunk_texts)


async def embed_query(query_text: str) -> list[float]:
    if not query_text:
        return []
    results = await asyncio.to_thread(_embed_sync, [query_text])
    return results[0] if results else []
