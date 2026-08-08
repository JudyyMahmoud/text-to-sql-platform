from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """
    Returns an OpenAI-compatible client for CHAT only (SQL generation and
    answer generation). This works with OpenAI itself, Groq, or any other
    OpenAI-compatible endpoint — just set OPENAI_BASE_URL and LLM_MODEL in
    .env. Note: this client is NOT used for embeddings; see
    services/documents/embedding_service.py, which runs embeddings locally
    since not every provider (e.g. Groq) offers an embeddings API.
    """
    global _client
    if _client is None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your .env file. "
                "This can be an OpenAI key, a Groq key (with OPENAI_BASE_URL="
                "https://api.groq.com/openai/v1), or any other OpenAI-compatible provider."
            )
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
    return _client


async def chat_completion(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    client = get_client()
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""
