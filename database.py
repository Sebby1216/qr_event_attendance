from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, event
from datetime import datetime
import asyncio

# Use aiosqlite driver
DATABASE_URL = "sqlite+aiosqlite:///./attendance.db"

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Enable WAL mode for better concurrency on SQLite
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    middle = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    program = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    section = Column(String(1), nullable=False)
    
    attendance_records = relationship("Attendance", back_populates="student")

class Attendance(Base):
    __tablename__ = "attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    checkin_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    checkout_time = Column(DateTime, nullable=True)
    
    student = relationship("Student", back_populates="attendance_records")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user") # "admin" or "user"

async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

# Note: Base.metadata.create_all(bind=engine) is sync and won't work directly here.
# We will handle this in main.py via lifespan events.
