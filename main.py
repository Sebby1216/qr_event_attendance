from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import engine, Base, SessionLocal, User
from utils import start_time_sync, hash_password
from routers import home, students, qr, attendance, dashboard, export, auth
from sqlalchemy import select
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and seed data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    start_time_sync()
    
    # Seed initial admin
    async with SessionLocal() as db:
        result = await db.execute(select(User).filter(User.student_id == "MA22_IT_02598"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            print("Seeding initial admin account...")
            new_admin = User(
                student_id="MA22_IT_02598",
                password_hash=hash_password("HendeAwku@1"),
                role="admin"
            )
            db.add(new_admin)
            await db.commit()
            print("Admin account created.")
    
    yield
    # Shutdown logic if needed

app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(students.router)
app.include_router(qr.router)
app.include_router(attendance.router)
app.include_router(dashboard.router)
app.include_router(export.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
