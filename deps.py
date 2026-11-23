from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Event, User, get_db
from utils import verify_session_token


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("session_token")
    if not token:
        return None
    data = verify_session_token(token)
    if not data:
        return None
    result = await db.execute(select(User).filter(User.student_id == data.get("sub")))
    user = result.scalar_one_or_none()
    if user and user.disabled:
        return None
    return user


async def require_login(request: Request, user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            detail="Not authenticated",
            headers={"Location": "/login"},
        )
    return user


async def require_admin(user: User = Depends(require_login)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


async def require_staff(user: User = Depends(require_login)):
    if user.role not in ("admin", "event_staff"):
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


async def get_active_event(request: Request, db: AsyncSession = Depends(get_db)):
    event_id = request.cookies.get("active_event_id")
    if event_id and event_id.isdigit():
        result = await db.execute(select(Event).filter(Event.id == int(event_id)))
        event = result.scalar_one_or_none()
        if event:
            return event

    result = await db.execute(
        select(Event).filter(Event.status == "open").order_by(Event.created_at.desc())
    )
    event = result.scalars().first()
    if event:
        return event

    result = await db.execute(select(Event).order_by(Event.created_at.desc()))
    return result.scalars().first()


async def require_open_event(event=Depends(get_active_event)):
    if not event:
        raise HTTPException(status_code=400, detail="No active event. Create or select an event first.")
    if event.status != "open":
        raise HTTPException(status_code=400, detail="The active event is not open for scanning.")
    return event
