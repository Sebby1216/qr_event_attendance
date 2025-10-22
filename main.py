from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import get_db, Student, Attendance
from datetime import datetime, date
import qrcode
from io import BytesIO
import re
from pydantic import BaseModel

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
    
    if len(parts) < 3:
        return None
    
    last_part = parts[-1]
    match = re.match(r'^([A-Z]{2,10})([1-9])([A-Z])$', last_part)
    
    if not match:
        return None
    
    program = match.group(1)
    year = int(match.group(2))
    section = match.group(3)
    
    name_parts = parts[:-1]
    
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
    middle_part = f" {student.middle}" if student.middle else ""
    return f"{student.first_name}{middle_part} {student.last_name} {student.program} {student.year}{student.section}"

@app.get("/", response_class=HTMLResponse)
async def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Attendance System</title></head>
    <body>
        <h1>QR Attendance System</h1>
        <ul>
            <li><a href="/add-student">Add Student</a></li>
            <li><a href="/generate-qr">Generate QR Codes</a></li>
            <li><a href="/scan">Scan QR Code</a></li>
            <li><a href="/live">Live Attendance</a></li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/add-student", response_class=HTMLResponse)
async def add_student_form():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Add Student</title></head>
    <body>
        <h1>Add Student</h1>
        <form id="studentForm">
            <label>First Name: <input type="text" name="first_name" required></label><br><br>
            <label>Middle Initial/Name: <input type="text" name="middle"></label><br><br>
            <label>Last Name: <input type="text" name="last_name" required></label><br><br>
            <label>Program: <input type="text" name="program" required placeholder="e.g., BSIT"></label><br><br>
            <label>Year: <input type="number" name="year" min="1" max="9" required></label><br><br>
            <label>Section: <input type="text" name="section" maxlength="1" required placeholder="A"></label><br><br>
            <button type="submit">Add Student</button>
        </form>
        <div id="message"></div>
        <br>
        <a href="/">Back to Home</a>
        
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
            document.getElementById('message').innerHTML = response.ok ? 
                '<p style="color:green">Student added successfully!</p>' : 
                '<p style="color:red">Error: ' + result.detail + '</p>';
            
            if (response.ok) {
                e.target.reset();
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
    students = db.query(Student).all()
    
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
            <td><a href="/qr/{student.id}.png" download="{student.last_name}_{student.first_name}_QR.png">Download</a></td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Generate QR Codes</title></head>
    <body>
        <h1>Student QR Codes</h1>
        <table border="1">
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
        <br>
        <a href="/">Back to Home</a>
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
    <head><title>Scan QR Code</title></head>
    <body>
        <h1>Scan QR Code for Check-in</h1>
        <video id="video" width="400" height="300" autoplay></video>
        <canvas id="canvas" hidden></canvas>
        <div id="output"></div>
        <br>
        <a href="/">Back to Home</a>
        
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
                output.innerHTML = '<p style="color:red">Camera access denied: ' + err + '</p>';
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
                    output.innerHTML = '<p>Processing...</p>';
                    
                    fetch('/checkin', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({text: code.data})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            output.innerHTML = '<p style="color:green">Check-in successful!</p>';
                        } else if (data.status === 'duplicate') {
                            output.innerHTML = '<p style="color:orange">Already checked in today!</p>';
                        } else {
                            output.innerHTML = '<p style="color:red">' + data.message + '</p>';
                        }
                        setTimeout(() => {
                            scanning = true;
                            output.innerHTML = '';
                        }, 2000);
                    })
                    .catch(err => {
                        output.innerHTML = '<p style="color:red">Error: ' + err + '</p>';
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
        student = Student(**parsed)
        db.add(student)
        db.commit()
        db.refresh(student)
    
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
    <head><title>Live Attendance</title></head>
    <body>
        <h1>Live Attendance</h1>
        <div id="attendance"></div>
        <br>
        <a href="/">Back to Home</a>
        
        <script>
        async function refreshAttendance() {
            const response = await fetch('/api/attendance');
            const data = await response.json();
            
            let html = '';
            for (const yearData of data) {
                html += '<h2>Year ' + yearData.year + ' (Total: ' + yearData.total + ')</h2>';
                for (const programData of yearData.programs) {
                    html += '<h3>' + programData.program + ' (Total: ' + programData.total + ')</h3>';
                    for (const sectionData of programData.sections) {
                        html += '<h4>Section ' + sectionData.section + ' (Total: ' + sectionData.total + ')</h4>';
                        html += '<ul>';
                        for (const student of sectionData.students) {
                            html += '<li>' + student.last_name + ', ' + student.first_name + 
                                   (student.middle ? ' ' + student.middle : '') + 
                                   ' - ' + student.checkin_time + '</li>';
                        }
                        html += '</ul>';
                    }
                }
            }
            
            document.getElementById('attendance').innerHTML = html || '<p>No check-ins yet.</p>';
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
