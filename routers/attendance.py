from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from database import get_db, Student, Attendance
from schemas import CheckinRequest
from utils import parse_qr_text, get_network_time, manager
from routers.auth import require_login
from datetime import datetime, date
import json

router = APIRouter()

@router.get("/scan", response_class=HTMLResponse)
async def scan_page(user=Depends(require_login)):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scan QR Code - Check In</title>
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
            .logout-link {
                position: absolute;
                top: 20px;
                right: 20px;
                color: #ff4444;
                text-decoration: none;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <a href="/logout" class="logout-link">Logout</a>
        <div class="container">
            <h1>📷 Scan QR Code - Check In</h1>
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
                            output.innerHTML = '<p class="success">✓ ' + data.fullname + ' - ' + data.year + '-' + data.section + ' Checked In!</p>';
                        } else if (data.status === 'duplicate') {
                            output.innerHTML = '<p class="duplicate">⚠ Already checked in!</p>';
                        } else if (data.status === 'not_found') {
                            output.innerHTML = '<p class="error">✗ Student not found.</p>';
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

@router.post("/checkin")
async def checkin(request: CheckinRequest, db: AsyncSession = Depends(get_db), user=Depends(require_login)):
    parsed = parse_qr_text(request.text)
    
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid QR code format")
    
    # Find student
    result = await db.execute(select(Student).filter(
        Student.first_name == parsed['first_name'],
        Student.middle == parsed['middle'],
        Student.last_name == parsed['last_name'],
        Student.program == parsed['program'],
        Student.year == parsed['year'],
        Student.section == parsed['section']
    ))
    student = result.scalar_one_or_none()
    
    if not student:
        try:
            student = Student(**parsed)
            db.add(student)
            await db.commit()
            await db.refresh(student)
        except IntegrityError:
            await db.rollback()
            result = await db.execute(select(Student).filter(
                Student.first_name == parsed['first_name'],
                Student.middle == parsed['middle'],
                Student.last_name == parsed['last_name'],
                Student.program == parsed['program'],
                Student.year == parsed['year'],
                Student.section == parsed['section']
            ))
            student = result.scalar_one_or_none()
    
    today = datetime.utcnow().date()
    result = await db.execute(select(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.checkin_time >= datetime.combine(today, datetime.min.time()),
        Attendance.checkout_time == None
    ))
    existing_today = result.scalar_one_or_none()
    
    if existing_today:
        return {"status": "duplicate"}
    
    attendance = Attendance(student_id=student.id, checkin_time=get_network_time())
    db.add(attendance)
    await db.commit()
    
    # Broadcast update
    fullname = f"{student.first_name} {student.last_name}".strip()
    await manager.broadcast(json.dumps({
        "type": "checkin",
        "student": fullname,
        "program": student.program,
        "year": student.year,
        "section": student.section,
        "time": attendance.checkin_time.strftime("%H:%M:%S")
    }))
    
    return {
        "status": "ok",
        "fullname": fullname,
        "year": student.year,
        "section": student.section
    }

@router.get("/scan-checkout", response_class=HTMLResponse)
async def scan_checkout_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scan QR Code - Check Out</title>
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
            <h1>📷 Scan QR Code - Check Out</h1>
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
                    
                    fetch('/checkout', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({text: code.data})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            output.innerHTML = '<p class="success">✓ Check-out successful!</p>';
                        } else if (data.status === 'not_checked_in') {
                            output.innerHTML = '<p class="duplicate">⚠ Not checked in today!</p>';
                        } else if (data.status === 'not_found') {
                            output.innerHTML = '<p class="error">✗ Student not found.</p>';
                        }
                         else {
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

@router.post("/checkout")
async def checkout(request: CheckinRequest, db: AsyncSession = Depends(get_db)):
    parsed = parse_qr_text(request.text)
    
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid QR code format")
    
    result = await db.execute(select(Student).filter(
        Student.first_name == parsed['first_name'],
        Student.middle == parsed['middle'],
        Student.last_name == parsed['last_name'],
        Student.program == parsed['program'],
        Student.year == parsed['year'],
        Student.section == parsed['section']
    ))
    student = result.scalar_one_or_none()
    
    if not student:
        return {"status": "not_found"}
    
    today = datetime.utcnow().date()
    
    result = await db.execute(select(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.checkout_time == None,
        Attendance.checkin_time >= datetime.combine(today, datetime.min.time())
    ))
    attendance = result.scalar_one_or_none()
    
    if not attendance:
        return {"status": "not_checked_in"}
    
    attendance.checkout_time = get_network_time()
    await db.commit()
    
    # Broadcast update
    fullname = f"{student.first_name} {student.last_name}".strip()
    await manager.broadcast(json.dumps({
        "type": "checkout",
        "student": fullname,
        "program": student.program,
        "year": student.year,
        "section": student.section,
        "time": attendance.checkout_time.strftime("%H:%M:%S")
    }))
    
    return {"status": "ok"}
