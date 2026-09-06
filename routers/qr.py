from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db, Student
from utils import generate_qr_text
from routers.auth import require_admin
import qrcode
from io import BytesIO
import zipfile

router = APIRouter()

@router.get("/generate-qr", response_class=HTMLResponse)
async def generate_qr_page(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(Student).order_by(Student.program, Student.year, Student.section, Student.last_name))
    students = result.scalars().all()
    
    years = sorted(set(s.year for s in students))
    sections = sorted(set(s.section for s in students))
    
    rows = ""
    for student in students:
        # qr_text = generate_qr_text(student) # Unused
        rows += f"""
        <tr class="student-row" data-year="{student.year}" data-section="{student.section}">
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
    
    year_options = '<option value="">All Years</option>'
    for year in years:
        year_options += f'<option value="{year}">{year}</option>'
    
    section_options = '<option value="">All Sections</option>'
    for section in sections:
        section_options += f'<option value="{section}">{section}</option>'
    
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
                margin-bottom: 30px;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
            }}
            .filter-section {{
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 30px;
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
                align-items: center;
            }}
            .filter-group {{
                display: flex;
                gap: 10px;
                align-items: center;
            }}
            .filter-group label {{
                color: #ffd700;
                font-weight: bold;
            }}
            select {{
                padding: 8px 15px;
                background: rgba(26, 0, 51, 0.8);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                cursor: pointer;
                transition: all 0.3s ease;
            }}
            select:focus {{
                outline: none;
                border-color: #fff;
                box-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
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
            .batch-download-btn {{
                padding: 10px 20px;
                background: #00aa00;
                color: #fff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s ease;
            }}
            .batch-download-btn:hover {{
                background: #00cc00;
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
            <h1>📱 Generate QR Codes</h1>
            <div class="filter-section">
                <div class="filter-group">
                    <label>Filter by Year:</label>
                    <select id="yearFilter" onchange="filterTable()">
                        {year_options}
                    </select>
                </div>
                <div class="filter-group">
                    <label>Filter by Section:</label>
                    <select id="sectionFilter" onchange="filterTable()">
                        {section_options}
                    </select>
                </div>
                <button class="batch-download-btn" onclick="downloadBatch()">⬇️ Download Selected QRs as ZIP</button>
            </div>
            <div class="table-wrapper">
                <table>
                    <thead>
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
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
            <center><a href="/" class="back-link">🏠 Back to Home</a></center>
        </div>
        
        <script>
        function filterTable() {{
            const yearFilter = document.getElementById('yearFilter').value;
            const sectionFilter = document.getElementById('sectionFilter').value;
            const rows = document.querySelectorAll('.student-row');
            
            rows.forEach(row => {{
                const year = row.getAttribute('data-year');
                const section = row.getAttribute('data-section');
                
                let show = true;
                if (yearFilter && year !== yearFilter) show = false;
                if (sectionFilter && section !== sectionFilter) show = false;
                
                row.style.display = show ? '' : 'none';
            }});
        }}

        function downloadBatch() {{
            const year = document.getElementById('yearFilter').value;
            const section = document.getElementById('sectionFilter').value;
            
            if (!year || !section) {{
                alert('Please select both a Year and Section to download');
                return;
            }}
            
            window.location.href = `/download-qr-batch?year=${{year}}&section=${{section}}`;
        }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@router.get("/qr/{student_id}.png")
async def get_qr(student_id: int, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(Student).filter(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    qr_text = generate_qr_text(student)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_text)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    return StreamingResponse(iter([img_buffer.getvalue()]), media_type="image/png")

@router.get("/download-qr-batch")
async def download_qr_batch(year: int, section: str, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    
    result = await db.execute(select(Student).filter(
        Student.year == year,
        Student.section == section
    ).order_by(Student.last_name, Student.first_name))
    students = result.scalars().all()
    
    if not students:
        raise HTTPException(status_code=404, detail="No students found for this year and section")
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for student in students:
            qr_text = generate_qr_text(student)
            
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(qr_text)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            img_buffer = BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            filename = f"{student.last_name}_{student.first_name}_QR.png"
            zip_file.writestr(filename, img_buffer.getvalue())
    
    zip_buffer.seek(0)
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=QR_Year{year}_Section{section}.zip"}
    )
