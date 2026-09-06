from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db, User
from utils import hash_password, verify_password, create_session_token, verify_session_token

router = APIRouter()

# --- Auth Dependencies ---
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("session_token")
    if not token:
        return None
    
    data = verify_session_token(token)
    if not data:
        return None
        
    result = await db.execute(select(User).filter(User.student_id == data.get("sub")))
    user = result.scalar_one_or_none()
    return user

async def require_login(request: Request, user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            detail="Not authenticated",
            headers={"Location": "/login"}
        )
    return user

async def require_admin(user: User = Depends(require_login)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

# --- Routes ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # If already logged in, redirect to appropriate page
    token = request.cookies.get("session_token")
    if token:
        data = verify_session_token(token)
        if data:
            # Simple redirect based on role (can be improved)
            return RedirectResponse(url="/", status_code=302)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                background: linear-gradient(135deg, #1a0033 0%, #2d004d 100%);
                color: #ffd700;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .login-box {
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                padding: 40px;
                width: 100%;
                max-width: 400px;
                text-align: center;
                box-shadow: 0 0 20px rgba(255, 215, 0, 0.2);
            }
            h1 { margin-bottom: 30px; color: #ffd700; }
            input {
                width: 100%;
                padding: 12px;
                margin-bottom: 20px;
                background: rgba(26, 0, 51, 0.8);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                font-size: 16px;
            }
            button {
                width: 100%;
                padding: 12px;
                background: #ffd700;
                color: #1a0033;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }
            button:hover { transform: scale(1.02); }
            .error { color: #ff4444; margin-bottom: 15px; display: none; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h1>Login</h1>
            <p id="error-msg" class="error"></p>
            <form action="/login" method="post">
                <input type="text" name="student_id" placeholder="Student ID" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Sign In</button>
            </form>
        </div>
    </body>
    </html>
    """
    return html

@router.post("/login")
async def login(
    response: Response,
    student_id: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.student_id == student_id))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.password_hash):
        # Return HTML with error (simplest way without JS fetch)
        return HTMLResponse(
            content="""
            <script>
                alert('Invalid credentials');
                window.location.href = '/login';
            </script>
            """,
            status_code=200
        )
    
    # Create session
    token = create_session_token({"sub": user.student_id, "role": user.role})
    
    # Redirect to home for all users
    redirect_url = "/"
    
    resp = RedirectResponse(url=redirect_url, status_code=302)
    resp.set_cookie(key="session_token", value=token, httponly=True)
    return resp

@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("session_token")
    return resp

# --- Admin User Management ---

@router.get("/admin/create-user", response_class=HTMLResponse)
async def create_user_page(user: User = Depends(require_admin)):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Create User Account</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                background: linear-gradient(135deg, #1a0033 0%, #2d004d 100%);
                color: #ffd700;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 40px;
            }
            .container {
                background: rgba(45, 0, 77, 0.6);
                border: 3px solid #ffd700;
                border-radius: 15px;
                padding: 40px;
                width: 100%;
                max-width: 500px;
            }
            h1 { text-align: center; margin-bottom: 30px; color: #ffd700; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 8px; font-weight: bold; }
            input, select {
                width: 100%;
                padding: 12px;
                background: rgba(26, 0, 51, 0.8);
                border: 2px solid #ffd700;
                border-radius: 8px;
                color: #ffd700;
                font-size: 16px;
            }
            button {
                width: 100%;
                padding: 12px;
                background: #ffd700;
                color: #1a0033;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                margin-top: 10px;
            }
            button:hover { opacity: 0.9; }
            .back-link {
                display: block;
                text-align: center;
                margin-top: 20px;
                color: #ffd700;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Create Account</h1>
            <form action="/admin/create-user" method="post">
                <div class="form-group">
                    <label>Student ID (Username)</label>
                    <input type="text" name="student_id" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <div class="form-group">
                    <label>Role</label>
                    <select name="role">
                        <option value="user">User (Scan Only)</option>
                        <option value="admin">Admin (Full Access)</option>
                    </select>
                </div>
                <button type="submit">Create Account</button>
            </form>
            <a href="/" class="back-link">Back to Dashboard</a>
        </div>
    </body>
    </html>
    """
    return html

@router.post("/admin/create-user")
async def create_user(
    student_id: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    # Check if user exists
    result = await db.execute(select(User).filter(User.student_id == student_id))
    existing = result.scalar_one_or_none()
    
    if existing:
         return HTMLResponse(
            content="""<script>alert('User already exists'); window.history.back();</script>""",
            status_code=400
        )
    
    new_user = User(
        student_id=student_id,
        password_hash=hash_password(password),
        role=role
    )
    db.add(new_user)
    await db.commit()
    
    return HTMLResponse(
        content="""<script>alert('Account created successfully'); window.location.href = '/admin/create-user';</script>""",
        status_code=200
    )
