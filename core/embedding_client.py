from __future__ import annotations

from openai import AsyncOpenAI, OpenAI

from core.embedding_constants import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL

# OpenAI batch limit: max 2048 texts per request.
# We use a smaller batch to keep memory and request size reasonable.
_BATCH_SIZE = 100


def create_embeddings(texts: list[str], *, api_key: str) -> list[list[float]]:
    """Encode a list of texts into embedding vectors via OpenAI API.

    Handles batching internally — caller can pass any number of texts.
    Returns vectors in the same order as input texts.
    """
    client = OpenAI(api_key=api_key)
    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL, input=batch, dimensions=EMBEDDING_DIMENSIONS
        )
        all_vectors.extend([d.embedding for d in response.data])

    return all_vectors


def embed_query(text: str, *, api_key: str) -> list[float]:
    """Embed a single text (e.g. a user query) and return the vector."""
    vectors = create_embeddings([text], api_key=api_key)
    return vectors[0]


async def async_embed_query(text: str, *, client: AsyncOpenAI) -> list[float]:
    """Async variant of embed_query. Caller provides the AsyncOpenAI client."""
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL, input=[text], dimensions=EMBEDDING_DIMENSIONS
    )
    return response.data[0].embedding
