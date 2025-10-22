from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./attendance.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
    
    __table_args__ = (
        UniqueConstraint('first_name', 'middle', 'last_name', 'program', 'year', 'section', 
                        name='unique_student'),
    )

class Attendance(Base):
    __tablename__ = "attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    checkin_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    student = relationship("Student", back_populates="attendance_records")
    
    __table_args__ = (
        UniqueConstraint('student_id', 'checkin_time', name='unique_daily_checkin'),
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)
