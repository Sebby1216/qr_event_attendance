from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Attendance, Event, User, get_db
from deps import get_active_event, require_staff
from templating import render
from utils import write_audit

router = APIRouter()


def parse_date(value: str):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return date.today()


def parse_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


@router.get("/events")
async def events_page(
    request: Request,
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    active_event: Event | None = Depends(get_active_event),
):
    result = await db.execute(select(Event).order_by(Event.created_at.desc()))
    return render(
        request,
        "events/list.html",
        {
            "active_page": "events",
            "events": result.scalars().all(),
            "active_event": active_event,
        },
    )


@router.post("/events")
async def create_event(
    name: str = Form(...),
    event_date: str = Form(...),
    venue: str = Form(""),
    organizer: str = Form(""),
    checkin_open: str | None = Form(None),
    checkin_close: str | None = Form(None),
    checkout_open: str | None = Form(None),
    checkout_close: str | None = Form(None),
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    event = Event(
        name=name.strip(),
        event_date=parse_date(event_date),
        venue=venue.strip(),
        organizer=organizer.strip(),
        checkin_open=parse_datetime(checkin_open),
        checkin_close=parse_datetime(checkin_close),
        checkout_open=parse_datetime(checkout_open),
        checkout_close=parse_datetime(checkout_close),
        status="draft",
    )
    db.add(event)
    await db.flush()
    await write_audit(db, user.id, "create", "event", event.id, {"name": event.name})
    await db.commit()

    resp = RedirectResponse(url=f"/events/{event.id}", status_code=303)
    resp.set_cookie(key="active_event_id", value=str(event.id), samesite="lax")
    return resp


@router.get("/events/{event_id}")
async def event_detail(
    event_id: int,
    request: Request,
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return RedirectResponse(url="/events?msg=Event%20not%20found&type=error", status_code=303)

    attendance_result = await db.execute(
        select(Attendance).filter(Attendance.event_id == event_id)
    )
    records = attendance_result.scalars().all()
    checked_in = len(records)
    checked_out = sum(1 for record in records if record.checkout_time)
    return render(
        request,
        "events/detail.html",
        {
            "active_page": "events",
            "event": event,
            "checked_in": checked_in,
            "checked_out": checked_out,
            "inside": checked_in - checked_out,
        },
    )


@router.post("/events/{event_id}/select")
async def select_event(
    event_id: int,
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).filter(Event.id == event_id))
    if not result.scalar_one_or_none():
        return RedirectResponse(url="/events?msg=Event%20not%20found&type=error", status_code=303)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="active_event_id", value=str(event_id), samesite="lax")
    return resp


@router.post("/events/{event_id}/status")
async def set_event_status(
    event_id: int,
    status: str = Form(...),
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    if status not in ("draft", "open", "closed"):
        return RedirectResponse(url="/events?msg=Invalid%20status&type=error", status_code=303)
    result = await db.execute(select(Event).filter(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return RedirectResponse(url="/events?msg=Event%20not%20found&type=error", status_code=303)
    event.status = status
    await write_audit(db, user.id, "status", "event", event.id, {"status": status})
    await db.commit()
    return RedirectResponse(url=f"/events/{event_id}?msg=Event%20{status}&type=success", status_code=303)
