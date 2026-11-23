from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AuditLog, User, get_db
from deps import require_admin
from templating import render

router = APIRouter()


@router.get("/audit")
async def audit_page(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))
    return render(
        request,
        "audit/list.html",
        {"active_page": "audit", "entries": result.scalars().all()},
    )
