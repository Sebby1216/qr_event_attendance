import csv
import io
import json

from fastapi import APIRouter, Depends, File, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import ImportBatch, Student, User, get_db
from deps import require_staff
from schemas import StudentCreate
from templating import render
from utils import write_audit

router = APIRouter()

CSV_FIELDS = ["student_id", "first_name", "middle", "last_name", "program", "year", "section"]


def normalize_student_data(data: dict):
    return {
        "student_id": str(data.get("student_id", "")).strip(),
        "first_name": str(data.get("first_name", "")).strip(),
        "middle": str(data.get("middle", "") or "").strip(),
        "last_name": str(data.get("last_name", "")).strip(),
        "program": str(data.get("program", "")).strip().upper(),
        "year": int(data.get("year", 0)),
        "section": str(data.get("section", "")).strip().upper(),
    }


def validate_row(data: dict, known_ids: set[str], known_identities: set[tuple]):
    errors = []
    if not data["student_id"]:
        errors.append("student_id is required")
    elif data["student_id"] in known_ids:
        errors.append("duplicate student_id")
    if not data["first_name"]:
        errors.append("first_name is required")
    if not data["last_name"]:
        errors.append("last_name is required")
    if not data["program"]:
        errors.append("program is required")
    if not 1 <= data["year"] <= 9:
        errors.append("year must be 1-9")
    if len(data["section"]) != 1 or not data["section"].isalpha():
        errors.append("section must be one letter")
    identity = (
        data["first_name"], data["middle"], data["last_name"],
        data["program"], data["year"], data["section"],
    )
    if identity in known_identities:
        errors.append("duplicate student identity")
    return errors


@router.get("/students")
async def students_page(
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
    result = await db.execute(query.order_by(Student.program, Student.year, Student.section, Student.last_name))
    return render(
        request,
        "students/list.html",
        {"active_page": "students", "students": result.scalars().all(), "search": search},
    )


@router.get("/students/add")
async def add_student_page(request: Request, user: User = Depends(require_staff)):
    return render(request, "students/add.html", {"active_page": "students"})


@router.post("/students")
async def create_student(request: Request, user: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        payload = dict(await request.form())

    try:
        data = normalize_student_data(payload)
        validated = StudentCreate(**data)
    except Exception:
        return RedirectResponse(url="/students/add?msg=Invalid%20student%20data&type=error", status_code=303)

    duplicate_id = await db.execute(select(Student).filter(Student.student_id == validated.student_id))
    if duplicate_id.scalar_one_or_none():
        return RedirectResponse(url="/students/add?msg=Student%20ID%20already%20exists&type=error", status_code=303)

    student = Student(**validated.model_dump())
    db.add(student)
    await db.flush()
    await write_audit(db, user.id, "create", "student", student.id, {"student_id": student.student_id})
    await db.commit()
    return RedirectResponse(
        url=f"/qr?msg=Student%20{student.student_id}%20added&type=success",
        status_code=303,
    )


@router.get("/students/import")
async def import_page(request: Request, user: User = Depends(require_staff)):
    return render(request, "students/import.html", {"active_page": "import"})


@router.get("/students/import/template")
async def import_template(user: User = Depends(require_staff)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_FIELDS)
    writer.writerow(["MA22-00123", "Juan", "S.", "Dela Cruz", "BSIT", 3, "A"])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_template.csv"},
    )


@router.post("/students/import/preview")
async def import_preview(
    request: Request,
    file=File(...),
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    contents = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(contents))
    if reader.fieldnames is None or "student_id" not in [name.strip().lower() for name in reader.fieldnames]:
        return RedirectResponse(url="/students/import?msg=CSV%20must%20include%20student_id&type=error", status_code=303)

    result = await db.execute(select(Student))
    existing = result.scalars().all()
    known_ids = {student.student_id for student in existing}
    known_identities = {
        (s.first_name, s.middle, s.last_name, s.program, s.year, s.section) for s in existing
    }

    rows = []
    for raw in reader:
        cleaned = {str(k).strip().lower(): v for k, v in raw.items() if k}
        try:
            data = normalize_student_data(cleaned)
            errors = validate_row(data, known_ids, known_identities)
            data["errors"] = errors
            if not errors:
                known_ids.add(data["student_id"])
                known_identities.add(
                    (data["first_name"], data["middle"], data["last_name"], data["program"], data["year"], data["section"])
                )
        except Exception as exc:
            data = {"errors": [f"Invalid row: {exc}"]}
        rows.append(data)

    batch = ImportBatch(
        filename=file.filename or "students.csv",
        rows=json.dumps(rows),
        errors=json.dumps([row for row in rows if row.get("errors")]),
        status="preview",
    )
    db.add(batch)
    await db.flush()
    await db.commit()

    return render(
        request,
        "students/import_preview.html",
        {
            "active_page": "import",
            "batch": batch,
            "rows": rows,
            "valid_count": sum(1 for row in rows if not row.get("errors")),
            "error_count": sum(1 for row in rows if row.get("errors")),
        },
    )


@router.post("/students/import/confirm")
async def import_confirm(
    batch_id: int = Form(...),
    user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ImportBatch).filter(ImportBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch or batch.status != "preview":
        return RedirectResponse(url="/students/import?msg=Import%20batch%20not%20found&type=error", status_code=303)

    rows = json.loads(batch.rows)
    created = skipped = 0
    errors = []
    for row in rows:
        if row.get("errors"):
            skipped += 1
            errors.append({"row": row, "errors": row["errors"]})
            continue
        duplicate = await db.execute(select(Student).filter(Student.student_id == row["student_id"]))
        if duplicate.scalar_one_or_none():
            skipped += 1
            errors.append({"row": row, "errors": ["student_id already exists"]})
            continue
        db.add(Student(**{field: row[field] for field in CSV_FIELDS}))
        created += 1

    batch.status = "imported"
    batch.errors = json.dumps(errors)
    await write_audit(db, user.id, "import", "student", batch_id, {"created": created, "skipped": skipped})
    await db.commit()

    return RedirectResponse(
        url=f"/students?msg=Imported%20{created}%20students%2C%20skipped%20{skipped}&type=success",
        status_code=303,
    )
