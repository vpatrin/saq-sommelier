from core.embedding_client import embed_query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import backend_settings
from backend.repositories.recommendations import find_similar
from backend.schemas.product import ProductOut
from backend.schemas.recommendation import RecommendationOut
from backend.services.intent import parse_intent


async def recommend(db: AsyncSession, query: str) -> RecommendationOut:
    """Full recommendation pipeline: parse intent → embed → retrieve → respond."""
    intent = parse_intent(query)
    vector = embed_query(intent.semantic_query, api_key=backend_settings.OPENAI_API_KEY)
    products = await find_similar(db, intent, vector)

    return RecommendationOut(
        products=[ProductOut.model_validate(p) for p in products],
        intent=intent,
    )
