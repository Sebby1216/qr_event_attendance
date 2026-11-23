import base64
import hashlib
import hmac
import json
import threading
import time
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from database import AuditLog, Student


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()

SECRET_KEY = "mysecretkey"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password


def create_session_token(data: dict) -> str:
    json_str = json.dumps(data)
    encoded_data = base64.b64encode(json_str.encode()).decode()
    signature = hmac.new(SECRET_KEY.encode(), encoded_data.encode(), hashlib.sha256).hexdigest()
    return f"{encoded_data}.{signature}"


def verify_session_token(token: str) -> dict | None:
    try:
        encoded_data, signature = token.split(".")
        expected = hmac.new(SECRET_KEY.encode(), encoded_data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        return json.loads(base64.b64decode(encoded_data).decode())
    except Exception:
        return None


time_offset = 0


def sync_network_time():
    global time_offset
    time_offset = 0
    print("[Time Sync] Using system time (no NTP library installed).")


def get_network_time():
    return datetime.utcnow()


def periodic_time_sync():
    while True:
        time.sleep(1800)
        sync_network_time()


def start_time_sync():
    sync_thread = threading.Thread(target=periodic_time_sync, daemon=True)
    sync_thread.start()
    sync_network_time()


def parse_qr_text(text: str):
    try:
        data = json.loads(text)
        required = ("student_id", "first_name", "last_name", "program", "year", "section")
        if not isinstance(data, dict) or any(field not in data for field in required):
            return None
        return {
            "student_id": str(data["student_id"]),
            "first_name": str(data["first_name"]),
            "middle": str(data.get("middle", "")),
            "last_name": str(data["last_name"]),
            "program": str(data["program"]),
            "year": int(data["year"]),
            "section": str(data["section"]),
        }
    except Exception:
        return None


def generate_qr_text(student: Student):
    return json.dumps(
        {
            "student_id": student.student_id,
            "first_name": student.first_name,
            "middle": student.middle,
            "last_name": student.last_name,
            "program": student.program,
            "year": student.year,
            "section": student.section,
        }
    )


async def write_audit(
    db: AsyncSession,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
):
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=json.dumps(details) if details else None,
        )
    )
