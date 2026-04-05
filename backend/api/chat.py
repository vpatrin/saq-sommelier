from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_active_user
from backend.config import DEFAULT_LIMIT, MAX_LIMIT, RATE_LIMIT_LLM
from backend.db import get_db
from backend.rate_limit import get_user_or_ip, limiter
from backend.schemas.chat import (
    ChatIn,
    ChatMessageOut,
    ChatSessionDetailOut,
    ChatSessionOut,
    ChatSessionUpdateIn,
)
from backend.services.chat import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    send_message,
    update_session,
)
from core.db.models import User

router = APIRouter(prefix="/chat/sessions", tags=["chat"])


@router.post("", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def post_session(
    body: ChatIn,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    """Create a new chat session, titled from the first message."""
    return await create_session(db, user.id, body.message)


@router.get("", response_model=list[ChatSessionOut])
async def get_sessions(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionOut]:
    """List chat sessions for the current user, most recent first."""
    return await list_sessions(db, user.id, limit, offset)


@router.get("/{session_id}", response_model=ChatSessionDetailOut)
async def get_session_detail(
    session_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetailOut:
    """Get a chat session with full message history."""
    return await get_session(db, user.id, session_id)


@router.patch("/{session_id}", response_model=ChatSessionOut)
async def patch_session(
    session_id: int,
    body: ChatSessionUpdateIn,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    """Update a chat session's title."""
    return await update_session(db, user.id, session_id, body.title)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(
    session_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard-delete a chat session and all its messages."""
    await delete_session(db, user.id, session_id)


@router.post(
    "/{session_id}/messages",
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_LLM, key_func=get_user_or_ip)
async def post_message(
    request: Request,
    session_id: int,
    body: ChatIn,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageOut:
    """Send a message to a chat session and get the assistant's response."""
    return await send_message(db, user.id, session_id, body.message)
