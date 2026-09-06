from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import get_db, Student, Attendance
from utils import get_network_time, manager
from routers.auth import require_admin
from datetime import datetime

router = APIRouter()

@router.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        manager.disconnect(websocket)

@router.get("/live", response_class=HTMLResponse)
async def live_page(admin=Depends(require_admin)):
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
            .header-section {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                flex-wrap: wrap;
                gap: 20px;
            }
            h1 {
                text-align: center;
                font-size: 2.5em;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
                color: #ffd700;
                flex: 1;
                min-width: 300px;
            }
            .clear-btn {
                padding: 12px 24px;
                background: #ff4444;
                color: #fff;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s ease;
                font-size: 1em;
            }
            .clear-btn:hover {
                background: #ff0000;
                transform: scale(1.05);
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
            .status {
                font-size: 0.9em;
                color: rgba(255, 215, 0, 0.7);
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
            <div class="header-section">
                <h1>👥 Live Attendance</h1>
                <button class="clear-btn" onclick="clearAttendance()">🗑️ Clear All Attendance</button>
            </div>
            <div id="attendance"></div>
            <p class="auto-refresh">Auto-refreshing every 3 seconds...</p>
            <center><a href="/" class="back-link">🏠 Back to Home</a></center>
        </div>
        
        <script>
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard`);
        let needsRefresh = false;

        ws.onmessage = function(event) {
            // When any update comes in, mark as needing refresh
            needsRefresh = true;
        };

        ws.onopen = function() {
            console.log("Connected to real-time updates");
        };

        ws.onclose = function() {
            console.log("Disconnected from real-time updates");
            // Optional: try to reconnect
            setTimeout(() => {
                window.location.reload();
            }, 5000);
        };

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
                                       ' <span class="status">' + student.checkin_time + ' → ' + student.checkout_time + '</span></li>';
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

        function checkRefresh() {
            if (needsRefresh) {
                refreshAttendance();
                needsRefresh = false;
            }
        }
        
        function clearAttendance() {
            if (confirm('Are you sure you want to delete ALL attendance records? This cannot be undone!')) {
                fetch('/clear-attendance', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    refreshAttendance();
                    // Also notify others via WS if we wanted to be fancy, 
                    // but for now local refresh + WS broadcast from server (if implemented) is fine.
                    // Currently server doesn't broadcast on clear, but that's okay.
                })
                .catch(err => alert('Error: ' + err));
            }
        }
        
        refreshAttendance();
        setInterval(checkRefresh, 1000); // Throttled update check
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@router.get("/api/attendance")
async def get_attendance(db: AsyncSession = Depends(get_db)):
    today = datetime.utcnow().date()
    result = await db.execute(
        select(Attendance)
        .options(selectinload(Attendance.student))
        .join(Student)
        .filter(Attendance.checkin_time >= datetime.combine(today, datetime.min.time()))
    )
    attendances = result.scalars().all()
    
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
        
        checkout_time_str = 'N/A'
        if attendance.checkout_time:
            # Format checkout time relative to local time, not just UTC from DB
            local_checkout_time = attendance.checkout_time.replace(tzinfo=None) - datetime.utcnow() + get_network_time()
            checkout_time_str = local_checkout_time.strftime('%H:%M:%S')

        # Format checkin time relative to local time
        local_checkin_time = attendance.checkin_time.replace(tzinfo=None) - datetime.utcnow() + get_network_time()

        data_by_year[year][program][section].append({
            'first_name': student.first_name,
            'last_name': student.last_name,
            'checkin_time': local_checkin_time.strftime('%H:%M:%S'),
            'checkout_time': checkout_time_str
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

@router.post("/clear-attendance")
async def clear_attendance(db: AsyncSession = Depends(get_db)):
    try:
        from sqlalchemy import delete
        await db.execute(delete(Attendance))
        await db.commit()
        return {"status": "ok", "message": "All attendance records cleared"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
