import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import Attendance, Event, ExportLog, User, get_db
from deps import get_active_event, require_staff
from templating import render
from utils import write_audit

router = APIRouter()

ALL_COLUMNS = [
    "student_id", "first_name", "last_name", "program", "year", "section",
    "checkin_time", "checkout_time", "source", "station_id",
]


def filtered_records(records, date_from: str, date_to: str, status: str):
    result = []
    for record in records:
        if date_from:
            try:
                if record.checkin_time < datetime.fromisoformat(date_from):
                    continue
            except ValueError:
                pass
        if date_to:
            try:
                if record.checkin_time > datetime.fromisoformat(date_to):
                    continue
            except ValueError:
                pass
        if status == "inside" and record.checkout_time:
            continue
        if status == "out" and not record.checkout_time:
            continue
        result.append(record)
    return result


@router.get("/export")
async def export_page(
    request: Request,
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    active_event: Event | None = Depends(get_active_event),
):
    events = (await db.execute(select(Event).order_by(Event.created_at.desc()))).scalars().all()
    history = (await db.execute(select(ExportLog).order_by(ExportLog.created_at.desc()).limit(20))).scalars().all()
    return render(
        request,
        "export/export.html",
        {
            "active_page": "export",
            "events": events,
            "active_event": active_event,
            "history": history,
            "columns": ALL_COLUMNS,
        },
    )


@router.get("/api/export/preview")
async def export_preview(
    event_id: int = 0,
    date_from: str = "",
    date_to: str = "",
    status: str = "",
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    query = select(Attendance).options(selectinload(Attendance.student))
    if event_id:
        query = query.filter(Attendance.event_id == event_id)
    records = (await db.execute(query)).scalars().all()
    return {"rows": len(filtered_records(records, date_from, date_to, status))}


@router.get("/download-csv")
async def download_csv(
    event_id: int = 0,
    date_from: str = "",
    date_to: str = "",
    status: str = "",
    columns: str = "",
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    query = select(Attendance).options(selectinload(Attendance.student))
    if event_id:
        query = query.filter(Attendance.event_id == event_id)
    records = filtered_records((await db.execute(query)).scalars().all(), date_from, date_to, status)

    selected = [column for column in columns.split(",") if column in ALL_COLUMNS] or ALL_COLUMNS
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([column.replace("_", " ").title() for column in selected])
    for record in records:
        student = record.student
        values = {
            "student_id": student.student_id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "program": student.program,
            "year": student.year,
            "section": student.section,
            "checkin_time": record.checkin_time.strftime("%Y-%m-%d %H:%M:%S"),
            "checkout_time": record.checkout_time.strftime("%Y-%m-%d %H:%M:%S") if record.checkout_time else "N/A",
            "source": record.source,
            "station_id": record.station_id or "",
        }
        writer.writerow([values[column] for column in selected])

    log = ExportLog(
        event_id=event_id or None,
        actor_id=user.id,
        format="csv",
        filters=json.dumps({"date_from": date_from, "date_to": date_to, "status": status}),
        row_count=len(records),
        filename="attendance.csv",
    )
    db.add(log)
    await write_audit(db, user.id, "export", "attendance", event_id or None, {"rows": len(records), "format": "csv"})
    await db.commit()

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"},
    )
