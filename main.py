from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from database import Base, SessionLocal, User, engine
from routers import attendance, audit, auth, dashboard, events, export, home, qr, students
from utils import hash_password, start_time_sync, verify_session_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    start_time_sync()

    async with SessionLocal() as db:
        result = await db.execute(select(User).filter(User.student_id == "MA22_IT_02598"))
        if not result.scalar_one_or_none():
            db.add(
                User(
                    student_id="MA22_IT_02598",
                    password_hash=hash_password("HendeAwku@1"),
                    role="admin",
                )
            )
            await db.commit()

    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def attach_current_user(request: Request, call_next):
    token = request.cookies.get("session_token")
    if token:
        data = verify_session_token(token)
        if data:
            from sqlalchemy import select as _select

            async with SessionLocal() as db:
                result = await db.execute(_select(User).filter(User.student_id == data.get("sub")))
                user = result.scalar_one_or_none()
                if user and not user.disabled:
                    request.state.current_user = user
    return await call_next(request)


app.include_router(auth.router)
app.include_router(events.router)
app.include_router(home.router)
app.include_router(students.router)
app.include_router(qr.router)
app.include_router(attendance.router)
app.include_router(dashboard.router)
app.include_router(export.router)
app.include_router(audit.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
