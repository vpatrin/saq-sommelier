from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import ChatMessage, ChatSession


async def create_session(db: AsyncSession, user_id: int, title: str) -> ChatSession:
    session = ChatSession(user_id=user_id, title=title)
    db.add(session)
    await db.flush()
    return session


async def create_message(db: AsyncSession, session_id: int, role: str, content: str) -> ChatMessage:
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    await db.flush()
    return msg


async def find_by_id(db: AsyncSession, session_id: int) -> ChatSession | None:
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def find_by_user(
    db: AsyncSession, user_id: int, *, limit: int, offset: int
) -> list[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def find_messages(db: AsyncSession, session_id: int) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def update_title(db: AsyncSession, session: ChatSession, title: str) -> ChatSession:
    session.title = title
    await db.flush()
    return session


async def delete_session(db: AsyncSession, session_id: int) -> None:
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    await db.flush()
