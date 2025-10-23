from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db, Student, Attendance
from datetime import datetime, date
import qrcode
from io import BytesIO
import re
from pydantic import BaseModel
from typing import cast

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class StudentCreate(BaseModel):
    first_name: str
    middle: str
    last_name: str
    program: str
    year: int
    section: str

class CheckinRequest(BaseModel):
    text: str

def parse_qr_text(text: str):
    parts = text.strip().split()
    
    if len(parts) < 4:
        return None
    
    last_part = parts[-1]
    second_last_part = parts[-2]
    
    match_year_section = re.match(r'^([1-9])([A-Z])$', last_part)
    match_program = re.match(r'^[A-Z]{2,10}$', second_last_part)
    
    if not match_year_section or not match_program:
        return None
    
    program = second_last_part
    year = int(match_year_section.group(1))
    section = match_year_section.group(2)
    
    name_parts = parts[:-2]
    
    if len(name_parts) < 2:
        return None
    
    first_name = name_parts[0]
    last_name = name_parts[-1]
    middle = ' '.join(name_parts[1:-1]) if len(name_parts) > 2 else ''
    
    return {
        'first_name': first_name,
        'middle': middle,
        'last_name': last_name,
        'program': program,
        'year': year,
        'section': section
    }

def generate_qr_text(student: Student):
    middle_val = str(student.middle) if student.middle else ""
    middle_part = f" {middle_val}" if middle_val.strip() else ""
    return f"{student.first_name}{middle_part} {student.last_name} {student.program} {student.year}{student.section}"

@app.get("/", response_class=HTMLResponse)
async def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Attendance System</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: linear-gradient(135deg, #1a0033 0%, #2d004d 100%);
                color: #ffd700;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                padding: 40px;
            }
            h1 {
                text-align: center;
                font-size: 3em;
                margin-bottom: 50px;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
            }
            .menu {
                list-style: none;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }
            .menu li {
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                transition: all 0.3s ease;
            }
            .menu li:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(255, 215, 0, 0.3);
                background: rgba(45, 0, 77, 0.9);
            }
            .menu a {
                display: block;
                padding: 30px;
                text-decoration: none;
                color: #ffd700;
                font-size: 1.3em;
                font-weight: bold;
                text-align: center;
                transition: all 0.3s ease;
            }
            .menu a:hover {
                color: #fff;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>QR Attendance System</h1>
            <ul class="menu">
                <li><a href="/add-student">➕ Add Student</a></li>
                <li><a href="/generate-qr">📱 Generate QR Codes</a></li>
                <li><a href="/scan">📷 Scan QR Code</a></li>
                <li><a href="/live">👥 Live Attendance</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/add-student", response_class=HTMLResponse)
async def add_student_form():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Add Student</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: linear-gradient(135deg, #1a0033 0%, #2d004d 100%);
                color: #ffd700;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                padding: 40px;
            }
            h1 {
                text-align: center;
                font-size: 2.5em;
                margin-bottom: 40px;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
            }
            form {
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                padding: 30px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                font-weight: bold;
                color: #ffd700;
            }
            input {
                width: 100%;
                padding: 12px;
                background: rgba(26, 0, 51, 0.8);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                font-size: 1em;
                transition: all 0.3s ease;
            }
            input:focus {
                outline: none;
                border-color: #fff;
                box-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
            }
            input::placeholder {
                color: rgba(255, 215, 0, 0.5);
            }
            button {
                width: 100%;
                padding: 15px;
                background: #ffd700;
                color: #1a0033;
                border: none;
                border-radius: 8px;
                font-size: 1.2em;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 10px;
            }
            button:hover {
                background: #fff;
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(255, 215, 0, 0.4);
            }
            #message {
                margin-top: 20px;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
            }
            #message.success {
                background: rgba(0, 255, 0, 0.2);
                border: 2px solid #00ff00;
                color: #00ff00;
            }
            #message.error {
                background: rgba(255, 0, 0, 0.2);
                border: 2px solid #ff0000;
                color: #ff0000;
            }
            .back-link {
                display: inline-block;
                margin-top: 30px;
                padding: 12px 30px;
                background: rgba(45, 0, 77, 0.6);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                text-decoration: none;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            .back-link:hover {
                background: rgba(45, 0, 77, 0.9);
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>➕ Add Student</h1>
            <form id="studentForm">
                <div class="form-group">
                    <label>First Name</label>
                    <input type="text" name="first_name" required>
                </div>
                <div class="form-group">
                    <label>Middle Initial/Name</label>
                    <input type="text" name="middle">
                </div>
                <div class="form-group">
                    <label>Last Name</label>
                    <input type="text" name="last_name" required>
                </div>
                <div class="form-group">
                    <label>Program</label>
                    <input type="text" name="program" required placeholder="e.g., BSIT">
                </div>
                <div class="form-group">
                    <label>Year</label>
                    <input type="number" name="year" min="1" max="9" required>
                </div>
                <div class="form-group">
                    <label>Section</label>
                    <input type="text" name="section" maxlength="1" required placeholder="A">
                </div>
                <button type="submit">Add Student</button>
            </form>
            <div id="message"></div>
            <center><a href="/" class="back-link">🏠 Back to Home</a></center>
        </div>
        
        <script>
        document.getElementById('studentForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = {
                first_name: formData.get('first_name'),
                middle: formData.get('middle') || '',
                last_name: formData.get('last_name'),
                program: formData.get('program').toUpperCase(),
                year: parseInt(formData.get('year')),
                section: formData.get('section').toUpperCase()
            };
            
            const response = await fetch('/students', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            const msgDiv = document.getElementById('message');
            if (response.ok) {
                msgDiv.className = 'success';
                msgDiv.textContent = '✓ Student added successfully!';
                e.target.reset();
            } else {
                msgDiv.className = 'error';
                msgDiv.textContent = '✗ Error: ' + result.detail;
            }
        });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/students")
async def create_student(student: StudentCreate, db: Session = Depends(get_db)):
    existing = db.query(Student).filter(
        Student.first_name == student.first_name,
        Student.middle == student.middle,
        Student.last_name == student.last_name,
        Student.program == student.program,
        Student.year == student.year,
        Student.section == student.section
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Student already exists")
    
    db_student = Student(**student.dict())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return {"id": db_student.id, "message": "Student created"}

@app.get("/generate-qr", response_class=HTMLResponse)
async def generate_qr_page(db: Session = Depends(get_db)):
    students = db.query(Student).order_by(Student.program, Student.year, Student.section, Student.last_name).all()
    
    rows = ""
    for student in students:
        qr_text = generate_qr_text(student)
        rows += f"""
        <tr>
            <td>{student.first_name}</td>
            <td>{student.middle}</td>
            <td>{student.last_name}</td>
            <td>{student.program}</td>
            <td>{student.year}</td>
            <td>{student.section}</td>
            <td><img src="/qr/{student.id}.png" width="100"></td>
            <td><a class="download-btn" href="/qr/{student.id}.png" download="{student.last_name}_{student.first_name}_QR.png">📥 Download</a></td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Generate QR Codes</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                background: linear-gradient(135deg, #1a0033 0%, #2d004d 100%);
                color: #ffd700;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 40px 20px;
            }}
            h1 {{
                text-align: center;
                font-size: 2.5em;
                margin-bottom: 40px;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
            }}
            .table-wrapper {{
                overflow-x: auto;
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                padding: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th {{
                background: rgba(26, 0, 51, 0.8);
                color: #ffd700;
                padding: 15px;
                text-align: left;
                font-weight: bold;
                border-bottom: 2px solid #ffd700;
            }}
            td {{
                padding: 15px;
                border-bottom: 1px solid rgba(255, 215, 0, 0.3);
                color: #ffd700;
            }}
            tr:hover {{
                background: rgba(255, 215, 0, 0.1);
            }}
            img {{
                border: 2px solid #ffd700;
                border-radius: 8px;
                background: white;
                padding: 5px;
            }}
            .download-btn {{
                display: inline-block;
                padding: 8px 16px;
                background: #ffd700;
                color: #1a0033;
                text-decoration: none;
                border-radius: 6px;
                font-weight: bold;
                transition: all 0.3s ease;
            }}
            .download-btn:hover {{
                background: #fff;
                transform: scale(1.05);
            }}
            .back-link {{
                display: inline-block;
                margin-top: 30px;
                padding: 12px 30px;
                background: rgba(45, 0, 77, 0.6);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                text-decoration: none;
                font-weight: bold;
                transition: all 0.3s ease;
            }}
            .back-link:hover {{
                background: rgba(45, 0, 77, 0.9);
                transform: translateY(-2px);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📱 Student QR Codes</h1>
            <div class="table-wrapper">
                <table>
                    <tr>
                        <th>First Name</th>
                        <th>Middle</th>
                        <th>Last Name</th>
                        <th>Program</th>
                        <th>Year</th>
                        <th>Section</th>
                        <th>QR Code</th>
                        <th>Download</th>
                    </tr>
                    {rows}
                </table>
            </div>
            <center><a href="/" class="back-link">🏠 Back to Home</a></center>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/qr/{student_id}.png")
async def get_qr_code(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    qr_text = generate_qr_text(student)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_text)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")

@app.get("/scan", response_class=HTMLResponse)
async def scan_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scan QR Code</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: linear-gradient(135deg, #1a0033 0%, #2d004d 100%);
                color: #ffd700;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                padding: 40px;
                text-align: center;
            }
            h1 {
                font-size: 2.5em;
                margin-bottom: 40px;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
            }
            .video-wrapper {
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 30px;
            }
            video {
                width: 100%;
                max-width: 400px;
                border-radius: 10px;
                border: 2px solid #ffd700;
            }
            #output {
                min-height: 60px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 20px 0;
            }
            #output p {
                padding: 15px 30px;
                border-radius: 8px;
                font-size: 1.2em;
                font-weight: bold;
            }
            #output .success {
                background: rgba(0, 255, 0, 0.2);
                border: 2px solid #00ff00;
                color: #00ff00;
            }
            #output .duplicate {
                background: rgba(255, 165, 0, 0.2);
                border: 2px solid #ffa500;
                color: #ffa500;
            }
            #output .error {
                background: rgba(255, 0, 0, 0.2);
                border: 2px solid #ff0000;
                color: #ff0000;
            }
            #output .processing {
                background: rgba(255, 215, 0, 0.2);
                border: 2px solid #ffd700;
                color: #ffd700;
            }
            .back-link {
                display: inline-block;
                margin-top: 30px;
                padding: 12px 30px;
                background: rgba(45, 0, 77, 0.6);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                text-decoration: none;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            .back-link:hover {
                background: rgba(45, 0, 77, 0.9);
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📷 Scan QR Code</h1>
            <div class="video-wrapper">
                <video id="video" autoplay></video>
            </div>
            <canvas id="canvas" hidden></canvas>
            <div id="output"></div>
            <a href="/" class="back-link">🏠 Back to Home</a>
        </div>
        
        <script src="/static/js/jsQR.js"></script>
        <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const output = document.getElementById('output');
        const canvasContext = canvas.getContext('2d');
        
        let scanning = true;
        
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
            .then(stream => {
                video.srcObject = stream;
                video.setAttribute('playsinline', true);
                video.play();
                requestAnimationFrame(tick);
            })
            .catch(err => {
                output.innerHTML = '<p class="error">Camera access denied: ' + err + '</p>';
            });
        
        function tick() {
            if (video.readyState === video.HAVE_ENOUGH_DATA) {
                canvas.height = video.videoHeight;
                canvas.width = video.videoWidth;
                canvasContext.drawImage(video, 0, 0, canvas.width, canvas.height);
                const imageData = canvasContext.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height, {
                    inversionAttempts: "dontInvert",
                });
                
                if (code && scanning) {
                    scanning = false;
                    output.innerHTML = '<p class="processing">⏳ Processing...</p>';
                    
                    fetch('/checkin', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({text: code.data})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            output.innerHTML = '<p class="success">✓ Check-in successful!</p>';
                        } else if (data.status === 'duplicate') {
                            output.innerHTML = '<p class="duplicate">⚠ Already checked in today!</p>';
                        } else {
                            output.innerHTML = '<p class="error">✗ ' + (data.message || 'Error occurred') + '</p>';
                        }
                        setTimeout(() => {
                            scanning = true;
                            output.innerHTML = '';
                        }, 2000);
                    })
                    .catch(err => {
                        output.innerHTML = '<p class="error">✗ Error: ' + err + '</p>';
                        setTimeout(() => {
                            scanning = true;
                            output.innerHTML = '';
                        }, 2000);
                    });
                }
            }
            requestAnimationFrame(tick);
        }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/checkin")
async def checkin(request: CheckinRequest, db: Session = Depends(get_db)):
    parsed = parse_qr_text(request.text)
    
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid QR code format")
    
    student = db.query(Student).filter(
        Student.first_name == parsed['first_name'],
        Student.middle == parsed['middle'],
        Student.last_name == parsed['last_name'],
        Student.program == parsed['program'],
        Student.year == parsed['year'],
        Student.section == parsed['section']
    ).first()
    
    if not student:
        try:
            student = Student(**parsed)
            db.add(student)
            db.commit()
            db.refresh(student)
        except IntegrityError:
            db.rollback()
            student = db.query(Student).filter(
                Student.first_name == parsed['first_name'],
                Student.middle == parsed['middle'],
                Student.last_name == parsed['last_name'],
                Student.program == parsed['program'],
                Student.year == parsed['year'],
                Student.section == parsed['section']
            ).first()
    
    today = date.today()
    existing_attendance = db.query(Attendance).filter(
        Attendance.student_id == student.id
    ).all()
    
    for attendance in existing_attendance:
        if attendance.checkin_time.date() == today:
            return {"status": "duplicate"}
    
    attendance = Attendance(student_id=student.id, checkin_time=datetime.utcnow())
    db.add(attendance)
    db.commit()
    
    return {"status": "ok"}

@app.get("/live", response_class=HTMLResponse)
async def live_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Attendance</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: linear-gradient(135deg, #1a0033 0%, #2d004d 100%);
                color: #ffd700;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                padding: 40px 20px;
            }
            h1 {
                text-align: center;
                font-size: 2.5em;
                margin-bottom: 40px;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
            }
            #attendance {
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                padding: 30px;
                min-height: 300px;
            }
            .year-section {
                margin-bottom: 30px;
            }
            .year-section h2 {
                color: #ffd700;
                font-size: 1.8em;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #ffd700;
            }
            .program-section {
                margin-left: 20px;
                margin-bottom: 20px;
            }
            .program-section h3 {
                color: #ffed4e;
                font-size: 1.5em;
                margin-bottom: 10px;
            }
            .section-group {
                margin-left: 40px;
                margin-bottom: 15px;
            }
            .section-group h4 {
                color: #ffe066;
                font-size: 1.2em;
                margin-bottom: 10px;
            }
            .student-list {
                list-style: none;
                margin-left: 60px;
            }
            .student-list li {
                padding: 10px;
                margin-bottom: 5px;
                background: rgba(26, 0, 51, 0.5);
                border-left: 3px solid #ffd700;
                border-radius: 5px;
                color: #ffd700;
                transition: all 0.3s ease;
            }
            .student-list li:hover {
                background: rgba(26, 0, 51, 0.8);
                border-left-width: 5px;
                transform: translateX(5px);
            }
            .no-data {
                text-align: center;
                color: rgba(255, 215, 0, 0.6);
                font-size: 1.2em;
                padding: 60px 20px;
            }
            .back-link {
                display: inline-block;
                margin-top: 30px;
                padding: 12px 30px;
                background: rgba(45, 0, 77, 0.6);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                text-decoration: none;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            .back-link:hover {
                background: rgba(45, 0, 77, 0.9);
                transform: translateY(-2px);
            }
            .auto-refresh {
                text-align: center;
                color: rgba(255, 215, 0, 0.6);
                font-size: 0.9em;
                margin-top: 15px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>👥 Live Attendance</h1>
            <div id="attendance"></div>
            <p class="auto-refresh">Auto-refreshing every 3 seconds...</p>
            <center><a href="/" class="back-link">🏠 Back to Home</a></center>
        </div>
        
        <script>
        async function refreshAttendance() {
            const response = await fetch('/api/attendance');
            const data = await response.json();
            
            let html = '';
            if (data.length === 0) {
                html = '<p class="no-data">No check-ins yet. Waiting for students to scan...</p>';
            } else {
                for (const yearData of data) {
                    html += '<div class="year-section">';
                    html += '<h2>Year ' + yearData.year + ' <span style="font-size:0.8em;">(Total: ' + yearData.total + ')</span></h2>';
                    for (const programData of yearData.programs) {
                        html += '<div class="program-section">';
                        html += '<h3>' + programData.program + ' <span style="font-size:0.8em;">(Total: ' + programData.total + ')</span></h3>';
                        for (const sectionData of programData.sections) {
                            html += '<div class="section-group">';
                            html += '<h4>Section ' + sectionData.section + ' <span style="font-size:0.8em;">(Total: ' + sectionData.total + ')</span></h4>';
                            html += '<ul class="student-list">';
                            for (const student of sectionData.students) {
                                html += '<li>' + student.last_name + ', ' + student.first_name + 
                                       (student.middle ? ' ' + student.middle : '') + 
                                       ' <span style="float:right; color: rgba(255,215,0,0.7);">⏱ ' + student.checkin_time + '</span></li>';
                            }
                            html += '</ul>';
                            html += '</div>';
                        }
                        html += '</div>';
                    }
                    html += '</div>';
                }
            }
            
            document.getElementById('attendance').innerHTML = html;
        }
        
        refreshAttendance();
        setInterval(refreshAttendance, 3000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/api/attendance")
async def get_attendance(db: Session = Depends(get_db)):
    attendances = db.query(Attendance).join(Student).all()
    
    data_by_year = {}
    for attendance in attendances:
        student = attendance.student
        year = student.year
        program = student.program
        section = student.section
        
        if year not in data_by_year:
            data_by_year[year] = {}
        if program not in data_by_year[year]:
            data_by_year[year][program] = {}
        if section not in data_by_year[year][program]:
            data_by_year[year][program][section] = []
        
        data_by_year[year][program][section].append({
            'first_name': student.first_name,
            'middle': student.middle,
            'last_name': student.last_name,
            'checkin_time': attendance.checkin_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    result = []
    for year in sorted(data_by_year.keys()):
        programs_list = []
        for program in sorted(data_by_year[year].keys()):
            sections_list = []
            for section in sorted(data_by_year[year][program].keys()):
                students = data_by_year[year][program][section]
                sections_list.append({
                    'section': section,
                    'total': len(students),
                    'students': students
                })
            programs_list.append({
                'program': program,
                'total': sum(s['total'] for s in sections_list),
                'sections': sections_list
            })
        result.append({
            'year': year,
            'total': sum(p['total'] for p in programs_list),
            'programs': programs_list
        })
    
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
