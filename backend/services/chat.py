from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import CONTEXT_WINDOW_TURNS, NON_WINE_MESSAGE
from backend.exceptions import ForbiddenError, NotFoundError
from backend.metrics import intent_classifications
from backend.repositories import chat as chat_repo
from backend.schemas.chat import (
    SESSION_TITLE_MAX_LENGTH,
    ChatMessageOut,
    ChatSessionDetailOut,
    ChatSessionOut,
)
from backend.schemas.recommendation import RecommendationOut
from backend.services.intent import parse_intent
from backend.services.recommendations import recommend
from backend.services.sommelier import sommelier_chat
from core.db.models import ChatMessage, ChatSession


async def _get_owned_session(db: AsyncSession, user_id: int, session_id: int) -> ChatSession:
    """Fetch a session and verify ownership. Raises NotFoundError or ForbiddenError."""
    session = await chat_repo.find_by_id(db, session_id)
    if session is None:
        raise NotFoundError("ChatSession", str(session_id))
    if session.user_id != user_id:
        raise ForbiddenError("Chat session access denied")
    return session


def _build_message_out(msg: ChatMessage) -> ChatMessageOut:
    """Convert a ChatMessage ORM object to the API response schema."""
    content: str | RecommendationOut
    if msg.role == "assistant":
        try:
            content = RecommendationOut.model_validate_json(msg.content)
        except (ValueError, ValidationError):
            logger.warning("Failed to deserialize assistant message id={}", msg.id)
            content = msg.content
    else:
        content = msg.content

    return ChatMessageOut(
        message_id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=content,
        created_at=msg.created_at,
    )


def _extract_multi_turn_context(
    messages: list[ChatMessage],
) -> tuple[list[str], str]:
    """Extract SKUs and conversation history from prior messages in a single pass.

    Returns (exclude_skus, conversation_history).
    """
    # SKUs from ALL messages (never re-recommend), history windowed to last N turns (token budget)
    skus: list[str] = []
    # Parse all assistant messages once, keep parsed results for history windowing
    parsed: dict[int, RecommendationOut | None] = {}
    for i, msg in enumerate(messages):
        if msg.role != "assistant":
            continue
        try:
            rec = RecommendationOut.model_validate_json(msg.content)
            skus.extend(p.product.sku for p in rec.products)
            parsed[i] = rec
        except (ValueError, ValidationError):
            parsed[i] = None

    # Build history from last N turns (no re-parsing needed)
    recent = messages[-(CONTEXT_WINDOW_TURNS * 2) :]
    offset = len(messages) - len(recent)
    lines: list[str] = []
    for j, msg in enumerate(recent):
        if msg.role == "user":
            lines.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            rec = parsed.get(offset + j)
            if rec is not None:
                lines.append(f"Assistant: {rec.summary}")
            else:
                lines.append(f"Assistant: {msg.content[:200]}")

    return skus, "\n".join(lines)


async def create_session(
    db: AsyncSession,
    user_id: int,
    message: str,
) -> ChatSessionOut:
    """Create a new chat session, titled from the first message."""
    title = message[:SESSION_TITLE_MAX_LENGTH].strip()
    session = await chat_repo.create_session(db, user_id, title)
    return ChatSessionOut.model_validate(session)


async def send_message(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    message: str,
) -> ChatMessageOut:
    """Send a message in an existing session: classify intent, route to the right service."""
    await _get_owned_session(db, user_id, session_id)

    # Save user message
    await chat_repo.create_message(db, session_id, "user", message)

    # Fetch history before intent classification so follow-up queries resolve correctly
    prior_messages = await chat_repo.find_messages(db, session_id)
    exclude_skus, conversation_history_str = _extract_multi_turn_context(prior_messages)
    # Coerce empty string → None once; all callers receive None for a fresh session
    conversation_history: str | None = conversation_history_str or None
    exclude_skus_opt: list[str] | None = exclude_skus or None

    # Pass last 2 turns (4 lines: user + assistant x2) to intent parser
    # so follow-ups ("what about lighter?") resolve correctly
    last_2_turns = "\n".join(conversation_history_str.splitlines()[-4:]) or None

    # Classify intent — Claude picks one of three tools
    intent = await parse_intent(message, conversation_history=last_2_turns)
    intent_classifications.labels(intent_type=intent.intent_type).inc()

    # Route based on intent_type — off_topic skips history entirely
    content: str | RecommendationOut
    if intent.intent_type == "off_topic":
        content = NON_WINE_MESSAGE
    elif intent.intent_type == "wine_chat":
        content = await sommelier_chat(message, conversation_history=conversation_history)
    elif intent.intent_type == "recommendation":
        content = await recommend(
            db,
            message,
            user_id=f"web:{user_id}",
            exclude_skus=exclude_skus_opt,
            conversation_history=conversation_history,
            intent=intent,
        )
    else:
        content = NON_WINE_MESSAGE

    # Save assistant response
    response_text = content.model_dump_json() if isinstance(content, RecommendationOut) else content
    assistant_msg = await chat_repo.create_message(db, session_id, "assistant", response_text)

    return ChatMessageOut(
        message_id=assistant_msg.id,
        session_id=session_id,
        role="assistant",
        content=content,
        created_at=assistant_msg.created_at,
    )


async def list_sessions(
    db: AsyncSession,
    user_id: int,
    limit: int,
    offset: int,
) -> list[ChatSessionOut]:
    """List chat sessions for a user, most recent first."""
    rows = await chat_repo.find_by_user(db, user_id, limit=limit, offset=offset)
    return [ChatSessionOut.model_validate(s) for s in rows]


async def get_session(
    db: AsyncSession,
    user_id: int,
    session_id: int,
) -> ChatSessionDetailOut:
    """Get a session with its full message history."""
    session = await _get_owned_session(db, user_id, session_id)
    messages = await chat_repo.find_messages(db, session_id)

    return ChatSessionDetailOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[_build_message_out(m) for m in messages],
    )


async def update_session(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    title: str,
) -> ChatSessionOut:
    """Update a chat session's title."""
    session = await _get_owned_session(db, user_id, session_id)
    session = await chat_repo.update_title(db, session, title)
    return ChatSessionOut.model_validate(session)


async def delete_session(
    db: AsyncSession,
    user_id: int,
    session_id: int,
) -> None:
    """Hard-delete a chat session (cascade deletes messages)."""
    await _get_owned_session(db, user_id, session_id)
    await chat_repo.delete_session(db, session_id)
