from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from deps import require_admin
from templating import render
from utils import create_session_token, hash_password, verify_password, write_audit

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render(request, "auth/login.html", {"active_page": "login", "error": None})


@router.post("/login")
async def login(
    request: Request,
    student_id: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime

    result = await db.execute(select(User).filter(User.student_id == student_id))
    user = result.scalar_one_or_none()

    if not user or user.disabled or not verify_password(password, user.password_hash):
        return render(
            request,
            "auth/login.html",
            {
                "active_page": "login",
                "error": "Invalid credentials or disabled account.",
                "student_id": student_id,
            },
            status_code=401,
        )

    user.last_login = datetime.utcnow()
    await db.commit()

    token = create_session_token({"sub": user.student_id, "role": user.role})
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("session_token")
    resp.delete_cookie("active_event_id")
    return resp


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.student_id))
    return render(
        request,
        "auth/accounts.html",
        {"active_page": "accounts", "accounts": result.scalars().all()},
    )


@router.post("/accounts")
async def create_account(
    request: Request,
    student_id: str = Form(...),
    password: str = Form(...),
    role: str = Form("scanner"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if role not in ("admin", "event_staff", "scanner"):
        role = "scanner"
    result = await db.execute(select(User).filter(User.student_id == student_id))
    if result.scalar_one_or_none():
        return RedirectResponse(url="/accounts?msg=Account%20already%20exists&type=error", status_code=303)

    db.add(User(student_id=student_id, password_hash=hash_password(password), role=role))
    await write_audit(db, admin.id, "create", "user", student_id, {"role": role})
    await db.commit()
    return RedirectResponse(url="/accounts?msg=Account%20created&type=success", status_code=303)


@router.post("/accounts/{user_id}/toggle")
async def toggle_account(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return RedirectResponse(url="/accounts?msg=Account%20not%20found&type=error", status_code=303)
    user.disabled = 0 if user.disabled else 1
    await write_audit(db, admin.id, "toggle", "user", user.student_id, {"disabled": bool(user.disabled)})
    await db.commit()
    return RedirectResponse(url="/accounts?msg=Account%20updated&type=success", status_code=303)
