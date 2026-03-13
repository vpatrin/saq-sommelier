from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import ForbiddenError, NotFoundError
from backend.repositories import chat as chat_repo
from backend.schemas.chat import (
    SESSION_TITLE_MAX_LENGTH,
    ChatMessageOut,
    ChatSessionDetailOut,
    ChatSessionOut,
)
from backend.schemas.recommendation import RecommendationOut
from backend.services.recommendations import recommend
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
    """Send a message in an existing session: save user msg, call recommend, save response."""
    await _get_owned_session(db, user_id, session_id)

    # Save user message
    await chat_repo.create_message(db, session_id, "user", message)

    # Call recommendation pipeline
    result = await recommend(db, message, user_id=f"web:{user_id}")

    # Save assistant response as JSON
    assistant_msg = await chat_repo.create_message(
        db, session_id, "assistant", result.model_dump_json()
    )

    return ChatMessageOut(
        message_id=assistant_msg.id,
        session_id=session_id,
        role="assistant",
        content=result,
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
