import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Attendance, Event, Student, User, get_db
from deps import get_active_event, get_current_user, require_login, require_open_event
from schemas import CheckinRequest, ScanRequest
from templating import render
from utils import get_network_time, manager, parse_qr_text, write_audit

router = APIRouter()


def _error(status: str, message: str, **extra):
    return {"status": status, "message": message, **extra}


def _within_window(event: Event, opened, closed, now: datetime):
    if opened and now < opened:
        return False
    if closed and now > closed:
        return False
    return True


async def _find_student(db: AsyncSession, student_id: str):
    result = await db.execute(select(Student).filter(Student.student_id == student_id))
    return result.scalar_one_or_none()


async def perform_scan(db: AsyncSession, event: Event, payload: ScanRequest, actor_id: int | None):
    mode = (payload.mode or "").lower()
    if mode not in ("in", "out"):
        return _error("error", "Unknown scan mode.")

    now = get_network_time()

    if payload.client_scan_id:
        result = await db.execute(
            select(Attendance).filter(Attendance.client_scan_id == payload.client_scan_id)
        )
        if result.scalar_one_or_none():
            return {"status": "ok", "replayed": True, "message": "Scan already processed."}

    student_id = payload.student_id
    source = "manual"
    if not student_id and payload.text:
        parsed = parse_qr_text(payload.text)
        if not parsed:
            return _error(
                "invalid_qr",
                "That QR code is not a valid attendance QR.",
                detail="Expected a JSON payload with student_id, name, program, year and section.",
            )
        student_id = parsed["student_id"]
        source = "qr"

    if not student_id:
        return _error("error", "No QR code or student ID was provided.")

    student = await _find_student(db, student_id.strip())
    if not student:
        return _error("not_registered", f"No student found for ID {student_id}.", student_id=student_id)

    if mode == "in":
        if not _within_window(event, event.checkin_open, event.checkin_close, now):
            return _error("outside_window", "Check-in is outside the event's check-in window.")

        result = await db.execute(
            select(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.event_id == event.id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return _error(
                "duplicate",
                f"{student.first_name} {student.last_name} is already checked in.",
                time=existing.checkin_time.strftime("%H:%M:%S"),
            )

        attendance = Attendance(
            student_id=student.id,
            event_id=event.id,
            checkin_time=now,
            station_id=payload.station_id,
            client_scan_id=payload.client_scan_id,
            source=source,
        )
        db.add(attendance)
        await db.flush()
        if source == "manual":
            await write_audit(
                db,
                actor_id,
                "manual_checkin",
                "attendance",
                attendance.id,
                {"student_id": student.student_id, "event_id": event.id},
            )
        await db.commit()

        fullname = f"{student.first_name} {student.last_name}".strip()
        await manager.broadcast(
            json.dumps(
                {
                    "type": "checkin",
                    "student": fullname,
                    "program": student.program,
                    "year": student.year,
                    "section": student.section,
                    "time": now.strftime("%H:%M:%S"),
                }
            )
        )
        return {
            "status": "ok",
            "direction": "in",
            "fullname": fullname,
            "student_id": student.student_id,
            "program": student.program,
            "year": student.year,
            "section": student.section,
            "time": now.strftime("%H:%M:%S"),
        }

    if not _within_window(event, event.checkout_open, event.checkout_close, now):
        return _error("outside_window", "Check-out is outside the event's check-out window.")

    result = await db.execute(
        select(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.event_id == event.id,
        )
    )
    attendance = result.scalar_one_or_none()
    if not attendance:
        return _error("not_checked_in", f"{student.first_name} {student.last_name} has not checked in.")
    if attendance.checkout_time:
        return _error(
            "already_checked_out",
            f"{student.first_name} {student.last_name} already checked out.",
            time=attendance.checkout_time.strftime("%H:%M:%S"),
        )

    attendance.checkout_time = now
    if source == "manual":
        await write_audit(
            db,
            actor_id,
            "manual_checkout",
            "attendance",
            attendance.id,
            {"student_id": student.student_id, "event_id": event.id},
        )
    await db.commit()

    fullname = f"{student.first_name} {student.last_name}".strip()
    await manager.broadcast(
        __import__("json").dumps(
            {
                "type": "checkout",
                "student": fullname,
                "program": student.program,
                "year": student.year,
                "section": student.section,
                "time": now.strftime("%H:%M:%S"),
            }
        )
    )
    return {
        "status": "ok",
        "direction": "out",
        "fullname": fullname,
        "student_id": student.student_id,
        "program": student.program,
        "year": student.year,
        "section": student.section,
        "time": now.strftime("%H:%M:%S"),
    }


@router.get("/scan", response_class=HTMLResponse)
async def scan_page(
    request: Request,
    user: User = Depends(require_login),
    event: Event | None = Depends(get_active_event),
):
    return render(
        request,
        "scan/scanner.html",
        {"active_page": "scan", "active_event": event},
    )


@router.post("/api/scan")
async def scan(
    payload: ScanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_login),
    event: Event = Depends(require_open_event),
):
    return await perform_scan(db, event, payload, user.id)


@router.post("/checkin")
async def legacy_checkin(
    payload: CheckinRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_login),
    event: Event = Depends(require_open_event),
):
    return await perform_scan(
        db, event, ScanRequest(mode="in", text=payload.text), user.id
    )


@router.post("/checkout")
async def legacy_checkout(
    payload: CheckinRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_login),
    event: Event = Depends(require_open_event),
):
    return await perform_scan(
        db, event, ScanRequest(mode="out", text=payload.text), user.id
    )
