from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    student_id: str
    first_name: str
    middle: str = ""
    last_name: str
    program: str
    year: int = Field(ge=1, le=9)
    section: str


class EventCreate(BaseModel):
    name: str
    event_date: str
    venue: str = ""
    organizer: str = ""
    checkin_open: str | None = None
    checkin_close: str | None = None
    checkout_open: str | None = None
    checkout_close: str | None = None


class ScanRequest(BaseModel):
    mode: str
    text: str | None = None
    student_id: str | None = None
    station_id: str | None = None
    client_scan_id: str | None = None


class CheckinRequest(BaseModel):
    text: str


class ImportConfirm(BaseModel):
    batch_id: int


class CorrectionRequest(BaseModel):
    action: str
    value: str | None = None


class ExportRequest(BaseModel):
    event_id: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    status: str | None = None
    columns: list[str] | None = None


class AccountCreate(BaseModel):
    student_id: str
    password: str
    role: str = "scanner"
