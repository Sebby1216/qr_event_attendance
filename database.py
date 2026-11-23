import os
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./attendance.db")

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    venue = Column(String, nullable=True)
    organizer = Column(String, nullable=True)
    checkin_open = Column(DateTime, nullable=True)
    checkin_close = Column(DateTime, nullable=True)
    checkout_open = Column(DateTime, nullable=True)
    checkout_close = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    attendance_records = relationship("Attendance", back_populates="event")
    imports = relationship("ImportBatch", back_populates="event")
    exports = relationship("ExportLog", back_populates="event")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=False)
    middle = Column(String, nullable=False, default="")
    last_name = Column(String, nullable=False)
    program = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    section = Column(String(1), nullable=False)

    attendance_records = relationship("Attendance", back_populates="student")

    __table_args__ = (
        UniqueConstraint(
            "first_name", "middle", "last_name", "program", "year", "section",
            name="uq_student_identity",
        ),
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    checkin_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    checkout_time = Column(DateTime, nullable=True)
    station_id = Column(String, nullable=True)
    client_scan_id = Column(String, unique=True, nullable=True)
    source = Column(String, nullable=False, default="qr")

    student = relationship("Student", back_populates="attendance_records")
    event = relationship("Event", back_populates="attendance_records")

    __table_args__ = (
        UniqueConstraint("student_id", "event_id", name="uq_attendance_student_event"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="scanner")
    disabled = Column(Integer, nullable=False, default=0)
    last_login = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    filename = Column(String, nullable=False)
    rows = Column(Text, nullable=False)
    errors = Column(Text, nullable=False, default="[]")
    status = Column(String, nullable=False, default="preview")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event", back_populates="imports")


class ExportLog(Base):
    __tablename__ = "export_log"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    format = Column(String, nullable=False, default="csv")
    filters = Column(Text, nullable=True)
    row_count = Column(Integer, nullable=False, default=0)
    filename = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event", back_populates="exports")


async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
