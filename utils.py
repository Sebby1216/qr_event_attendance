import threading
import time
import json
import hashlib
import hmac
import base64
from datetime import datetime
from database import Student
from fastapi import WebSocket

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Handle disconnected clients gracefully
                pass

manager = ConnectionManager()

# --- Auth Utils ---
SECRET_KEY = "mysecretkey" # Change this in production!

def hash_password(password: str) -> str:
    """Hash a password using SHA256 (simple implementation)."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password."""
    return hash_password(plain_password) == hashed_password

def create_session_token(data: dict) -> str:
    """Create a signed session token."""
    json_str = json.dumps(data)
    encoded_data = base64.b64encode(json_str.encode()).decode()
    signature = hmac.new(SECRET_KEY.encode(), encoded_data.encode(), hashlib.sha256).hexdigest()
    return f"{encoded_data}.{signature}"

def verify_session_token(token: str) -> dict | None:
    """Verify and decode a session token."""
    try:
        encoded_data, signature = token.split('.')
        expected_signature = hmac.new(SECRET_KEY.encode(), encoded_data.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_signature):
            json_str = base64.b64decode(encoded_data).decode()
            return json.loads(json_str)
        return None
    except:
        return None

# --- Time Sync Utils ---
# Global variable to store the time offset (default 0)
time_offset = 0

def sync_network_time():
    """
    Mock sync function.
    Since we are avoiding external libraries like ntplib,
    we will rely on the system time.
    """
    global time_offset
    time_offset = 0
    print("[Time Sync] Using system time (no NTP library installed).")

def get_network_time():
    """Get current time (using system time)"""
    return datetime.utcnow()

def periodic_time_sync():
    """Periodically sync time (placeholder)"""
    while True:
        time.sleep(1800)  # 30 minutes
        sync_network_time()

def start_time_sync():
    """Start periodic sync in background"""
    sync_thread = threading.Thread(target=periodic_time_sync, daemon=True)
    sync_thread.start()
    # Initial sync
    sync_network_time()

def parse_qr_text(text: str):
    try:
        data = json.loads(text)
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'program', 'year', 'section']
        for field in required_fields:
            if field not in data:
                return None
        
        return {
            'first_name': data['first_name'],
            'middle': data.get('middle', ''),
            'last_name': data['last_name'],
            'program': data['program'],
            'year': int(data['year']),
            'section': data['section']
        }
    except:
        return None

def generate_qr_text(student: Student):
    return json.dumps({
        "first_name": student.first_name,
        "middle": student.middle,
        "last_name": student.last_name,
        "program": student.program,
        "year": student.year,
        "section": student.section
    })
