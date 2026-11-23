from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import Attendance, Event, Student, User, get_db
from deps import get_active_event, require_login
from templating import render

router = APIRouter()


@router.get("/")
async def home(
    request: Request,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
    active_event: Event | None = Depends(get_active_event),
):
    records = []
    checked_in = checked_out = inside = not_arrived = exceptions = 0

    if active_event:
        result = await db.execute(
            select(Attendance)
            .options(selectinload(Attendance.student))
            .filter(Attendance.event_id == active_event.id)
            .order_by(Attendance.checkin_time.desc())
            .limit(8)
        )
        records = result.scalars().all()

        all_result = await db.execute(
            select(Attendance).filter(Attendance.event_id == active_event.id)
        )
        all_records = all_result.scalars().all()
        checked_in = len(all_records)
        checked_out = sum(1 for record in all_records if record.checkout_time)
        inside = checked_in - checked_out
        exceptions = sum(1 for record in all_records if record.source != "qr")

        total_students = await db.scalar(select(func.count()).select_from(Student))
        not_arrived = max((total_students or 0) - checked_in, 0)

    events_result = await db.execute(select(Event).order_by(Event.created_at.desc()))
    return render(
        request,
        "dashboard/home.html",
        {
            "active_page": "home",
            "active_event": active_event,
            "events": events_result.scalars().all(),
            "records": records,
            "checked_in": checked_in,
            "checked_out": checked_out,
            "inside": inside,
            "not_arrived": not_arrived,
            "exceptions": exceptions,
        },
    )
