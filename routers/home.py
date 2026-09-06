from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Student, User
from routers.auth import require_admin, require_login
import csv
import codecs

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home(user: User = Depends(require_login)):
    # Define menu items based on role
    menu_items = ""
    
    # Common items for all users (Admin and Regular)
    menu_items += """
        <li><a href="/scan">📷 Scan QR (Check-In)</a></li>
        <li><a href="/scan-checkout">📷 Scan QR (Check-Out)</a></li>
    """
    
    # Admin-only items
    if user.role == "admin":
        menu_items = """
        <li><a href="/add-student">➕ Add Student</a></li>
        <li><a href="/generate-qr">📱 Generate QR Codes For Students</a></li>
        <li><a href="/admin/create-user">👤 Create Account</a></li>
        <li>
            <form action="/upload-csv" method="post" enctype="multipart/form-data" id="uploadForm">
                 <input type="file" name="file" id="fileInput" accept=".csv" style="display: none;" onchange="document.getElementById('uploadForm').submit()">
                 <button type="button" onclick="document.getElementById('fileInput').click()">📂 Upload CSV</button>
            </form>
        </li>
        """ + menu_items + """
        <li><a href="/live">📊 Live Dashboard</a></li>
        <li><a href="/export">📥 Export Attendance</a></li>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Attendance System</title>
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
                max-width: 800px;
                margin: 0 auto;
                padding: 40px;
            }}
            h1 {{
                text-align: center;
                font-size: 3em;
                margin-bottom: 50px;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
            }}
            .menu {{
                list-style: none;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }}
            .menu li {{
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                transition: all 0.3s ease;
            }}
            .menu li:hover {{
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(255, 215, 0, 0.3);
                background: rgba(45, 0, 77, 0.9);
            }}
            .menu a, .menu button {{
                display: block;
                padding: 30px;
                text-decoration: none;
                color: #ffd700;
                font-size: 1.3em;
                font-weight: bold;
                text-align: center;
                transition: all 0.3s ease;
                background: none;
                border: none;
                cursor: pointer;
                width: 100%;
            }}
            .menu a:hover, .menu button:hover {{
                color: #fff;
            }}
            .menu li button {{
                padding: 30px;
            }}
            #message {{
                margin-top: 20px;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
            }}
            #message.success {{
                background: rgba(0, 255, 0, 0.2);
                border: 2px solid #00ff00;
                color: #00ff00;
            }}
            #message.error {{
                background: rgba(255, 0, 0, 0.2);
                border: 2px solid #ff0000;
                color: #ff0000;
            }}
            .logout-btn {{
                display: block;
                width: fit-content;
                margin: 20px auto 0;
                padding: 10px 20px;
                background: #ff4444;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: bold;
            }}
            .logout-btn:hover {{
                background: #ff0000;
            }}
            .role-badge {{
                text-align: center;
                margin-bottom: 20px;
                font-size: 1.2em;
                color: #ccc;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>SSIT QR Attendance System</h1>
            <div class="role-badge">Logged in as: {user.role.upper()} ({user.student_id})</div>
            <ul class="menu">
                {menu_items}
            </ul>
            <a href="/logout" class="logout-btn">Logout</a>
            <div id="message"></div>
        </div>
        <script>
            // Check for URL parameters to show messages
            const urlParams = new URLSearchParams(window.location.search);
            const msg = document.getElementById('message');
            
            if (urlParams.has('success')) {{
                msg.textContent = urlParams.get('success');
                msg.className = 'success';
                setTimeout(() => {{ msg.style.display = 'none'; }}, 3000);
            }}
            if (urlParams.has('error')) {{
                msg.textContent = urlParams.get('error');
                msg.className = 'error';
                setTimeout(() => {{ msg.style.display = 'none'; }}, 3000);
            }}
        </script>
    </body>
    </html>
    """
    return html

@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    try:
        csv_file = codecs.iterdecode(file.file, 'utf-8')
        reader = csv.DictReader(csv_file)
        
        count = 0
        for row in reader:
            # Check for required columns (case-insensitive keys if possible, but strict for now)
            # Expected headers: first_name, middle, last_name, program, year, section
            
            # Simple normalization of keys to lower case just in case
            row = {k.strip().lower(): v for k, v in row.items() if k}
            
            if not all(k in row for k in ('first_name', 'last_name', 'program', 'year', 'section')):
                continue
                
            new_student = Student(
                first_name=row['first_name'],
                middle=row.get('middle', ''),
                last_name=row['last_name'],
                program=row['program'],
                year=int(row['year']),
                section=row['section']
            )
            db.add(new_student)
            count += 1
            
        await db.commit()
        return RedirectResponse(url=f"/?success=Successfully uploaded {count} students", status_code=303)
    except Exception as e:
        await db.rollback()
        return RedirectResponse(url=f"/?error=Upload failed: {str(e)}", status_code=303)
