from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import get_db, Student, Attendance
from routers.auth import require_admin
import csv
from io import StringIO

router = APIRouter()

@router.get("/export", response_class=HTMLResponse)
async def export_page(admin=Depends(require_admin)):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Export Attendance</title>
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
            <h1>📥 Export Attendance</h1>
            <form id="exportForm">
                <!-- Updated button text to reflect exporting all attendance records -->
                <button type="submit">📥 Download All Attendance Records</button>
            </form>
            <center><a href="/" class="back-link">🏠 Back to Home</a></center>
        </div>
        
        <script>
        document.getElementById('exportForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            window.location.href = '/download-csv';
        });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@router.get("/download-csv")
async def download_csv(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(Attendance).options(selectinload(Attendance.student)))
    attendances = result.scalars().all()
    
    # Generate CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['First Name', 'Last Name', 'Program', 'Year', 'Section', 'Check-in Time', 'Check-out Time'])
    
    for attendance in attendances:
        student = attendance.student
        checkin_time = attendance.checkin_time.strftime('%Y-%m-%d %H:%M:%S')
        checkout_time = attendance.checkout_time.strftime('%Y-%m-%d %H:%M:%S') if attendance.checkout_time else 'N/A'
        
        writer.writerow([
            student.first_name,
            student.last_name,
            student.program,
            student.year,
            student.section,
            checkin_time,
            checkout_time
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"}
    )
