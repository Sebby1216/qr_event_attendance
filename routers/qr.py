import io
import zipfile

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import qrcode
from database import Student, User, get_db
from deps import require_staff
from templating import render
from utils import generate_qr_text, write_audit

router = APIRouter()


def parse_ids(ids: str):
    try:
        return [int(value) for value in ids.split(",") if value.strip().isdigit()]
    except Exception:
        return []


def qr_png(student: Student) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(generate_qr_text(student))
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def zip_response(students, filename_header: str):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for student in students:
            archive.writestr(
                f"{student.student_id}_{student.last_name}_{student.first_name}_QR.png",
                qr_png(student),
            )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename_header}"'},
    )


@router.get("/qr")
async def qr_page(
    request: Request,
    search: str = "",
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    query = select(Student)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Student.student_id.ilike(pattern),
                Student.first_name.ilike(pattern),
                Student.last_name.ilike(pattern),
                Student.program.ilike(pattern),
            )
        )
    result = await db.execute(
        query.order_by(Student.program, Student.year, Student.section, Student.last_name)
    )
    return render(
        request,
        "qr/manage.html",
        {"active_page": "qr", "students": result.scalars().all(), "search": search},
    )


@router.get("/qr/download")
async def download_selected(
    ids: str = "",
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    wanted = parse_ids(ids)
    if not wanted:
        return RedirectResponse(url="/qr?msg=No%20students%20selected&type=error", status_code=303)
    result = await db.execute(select(Student).filter(Student.id.in_(wanted)))
    return zip_response(result.scalars().all(), "selected_qr_codes.zip")


@router.get("/qr/download-all")
async def download_all(
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Student).order_by(Student.last_name, Student.first_name))
    return zip_response(result.scalars().all(), "all_qr_codes.zip")


@router.get("/qr/print")
async def print_sheet(
    request: Request,
    ids: str = "",
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    wanted = parse_ids(ids)
    query = select(Student)
    if wanted:
        query = query.filter(Student.id.in_(wanted))
    result = await db.execute(query.order_by(Student.program, Student.year, Student.section, Student.last_name))
    return render(
        request,
        "qr/print_sheet.html",
        {"students": result.scalars().all()},
    )


@router.post("/qr/regenerate/{student_id}")
async def regenerate_qr(
    student_id: int,
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Student).filter(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        return RedirectResponse(url="/qr?msg=Student%20not%20found&type=error", status_code=303)
    await write_audit(db, user.id, "regenerate_qr", "student", student.id, {"student_id": student.student_id})
    await db.commit()
    return RedirectResponse(url="/qr?msg=QR%20regenerated&type=success", status_code=303)


@router.get("/qr/{student_db_id}.png")
async def get_qr(
    student_db_id: int,
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Student).filter(Student.id == student_db_id))
    student = result.scalar_one_or_none()
    if not student:
        return StreamingResponse(iter([b""]), status_code=404, media_type="image/png")
    return StreamingResponse(iter([qr_png(student)]), media_type="image/png")
