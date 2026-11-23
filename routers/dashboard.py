import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import Attendance, Event, User, get_db
from deps import get_active_event, require_admin, require_login, require_staff
from schemas import CorrectionRequest
from templating import render
from utils import manager, write_audit

router = APIRouter()


@router.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket)


@router.get("/live")
async def live_page(
    request: Request,
    user: User = Depends(require_login),
    event: Event | None = Depends(get_active_event),
):
    return render(
        request,
        "live/control_room.html",
        {"active_page": "live", "active_event": event, "can_manage": user.role in ("admin", "event_staff")},
    )


@router.get("/api/attendance")
async def get_attendance(
    search: str = "",
    section: str = "",
    status: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_login),
    event: Event | None = Depends(get_active_event),
):
    if not event:
        return []

    query = (
        select(Attendance)
        .options(selectinload(Attendance.student))
        .filter(Attendance.event_id == event.id)
        .order_by(Attendance.checkin_time.desc())
    )
    result = await db.execute(query)
    records = result.scalars().all()

    filtered = []
    for record in records:
        student = record.student
        if section and student.section != section:
            continue
        if status == "inside" and record.checkout_time:
            continue
        if status == "out" and not record.checkout_time:
            continue
        if search:
            needle = search.lower()
            haystack = f"{student.student_id} {student.first_name} {student.last_name} {student.program}".lower()
            if needle not in haystack:
                continue
        filtered.append(record)

    grouped = {}
    for record in filtered:
        student = record.student
        year = str(student.year)
        program = student.program
        section_key = student.section
        grouped.setdefault(year, {}).setdefault(program, {}).setdefault(section_key, []).append(
            {
                "id": record.id,
                "student_id": student.student_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "checkin_time": record.checkin_time.strftime("%H:%M:%S"),
                "checkout_time": record.checkout_time.strftime("%H:%M:%S") if record.checkout_time else None,
                "inside": not bool(record.checkout_time),
                "source": record.source,
            }
        )

    payload = []
    for year in sorted(grouped, key=int):
        programs = []
        for program in sorted(grouped[year]):
            sections = []
            for section_key in sorted(grouped[year][program]):
                students = grouped[year][program][section_key]
                sections.append({"section": section_key, "total": len(students), "students": students})
            programs.append(
                {
                    "program": program,
                    "total": sum(section["total"] for section in sections),
                    "sections": sections,
                }
            )
        payload.append(
            {"year": year, "total": sum(program["total"] for program in programs), "programs": programs}
        )
    return payload


@router.post("/attendance/{record_id}/correction")
async def correct_attendance(
    record_id: int,
    payload: CorrectionRequest,
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Attendance).filter(Attendance.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        return {"status": "error", "message": "Record not found."}

    if payload.action == "delete":
        await db.delete(record)
        detail = {"action": "delete"}
    elif payload.action in ("checkin_time", "checkout_time"):
        try:
            corrected = datetime.fromisoformat(payload.value or "")
        except ValueError:
            return {"status": "error", "message": "Invalid timestamp."}
        setattr(record, payload.action, corrected)
        detail = {"action": payload.action, "value": payload.value}
    else:
        return {"status": "error", "message": "Unknown correction action."}

    await write_audit(db, user.id, "correction", "attendance", record_id, detail)
    await db.commit()
    await manager.broadcast(json.dumps({"type": "correction", "record_id": record_id}))
    return {"status": "ok"}


@router.post("/attendance/reset")
async def reset_attendance(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    event: Event = Depends(get_active_event),
):
    if not event:
        return RedirectResponse(url="/live?msg=No%20active%20event&type=error", status_code=303)
    count_result = await db.execute(
        select(Attendance).filter(Attendance.event_id == event.id)
    )
    count = len(count_result.scalars().all())
    await db.execute(delete(Attendance).filter(Attendance.event_id == event.id))
    await write_audit(db, user.id, "reset", "attendance", event.id, {"records": count})
    await db.commit()
    await manager.broadcast(json.dumps({"type": "reset", "event_id": event.id}))
    return RedirectResponse(url="/live?msg=Attendance%20reset&type=success", status_code=303)
