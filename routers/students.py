from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db, Student
from schemas import StudentCreate
from routers.auth import require_admin
import csv

router = APIRouter()

@router.get("/add-student", response_class=HTMLResponse)
async def add_student_form(admin=Depends(require_admin)):
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

@router.post("/students")
async def create_student(student: StudentCreate, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(Student).filter(
        Student.first_name == student.first_name,
        Student.middle == student.middle,
        Student.last_name == student.last_name,
        Student.program == student.program,
        Student.year == student.year,
        Student.section == student.section
    ))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Student already exists")
    
    db_student = Student(**student.dict())
    db.add(db_student)
    await db.commit()
    await db.refresh(db_student)
    return {"id": db_student.id, "message": "Student created"}

@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    contents = await file.read()
    csv_data = contents.decode('utf-8').splitlines()
    reader = csv.DictReader(csv_data)
    
    students_created = 0
    students_already_exist = 0
    
    for row in reader:
        student_data = {
            'first_name': row['first_name'],
            'middle': row.get('middle', ''),
            'last_name': row['last_name'],
            'program': row['program'],
            'year': int(row['year']),
            'section': row['section']
        }
        
        # Check if student already exists
        result = await db.execute(select(Student).filter(
            Student.first_name == student_data['first_name'],
            Student.middle == student_data['middle'],
            Student.last_name == student_data['last_name'],
            Student.program == student_data['program'],
            Student.year == student_data['year'],
            Student.section == student_data['section']
        ))
        existing_student = result.scalar_one_or_none()
        
        if not existing_student:
            student = Student(**student_data)
            db.add(student)
            students_created += 1
        else:
            students_already_exist += 1
    
    await db.commit()
    
    return {
        "status": "ok",
        "message": f"Added {students_created} new students. {students_already_exist} already existed.",
        "students_created": students_created,
        "students_skipped": students_already_exist
    }
