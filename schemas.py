from pydantic import BaseModel

class StudentCreate(BaseModel):
    first_name: str
    middle: str
    last_name: str
    program: str
    year: int
    section: str

class CheckinRequest(BaseModel):
    text: str
