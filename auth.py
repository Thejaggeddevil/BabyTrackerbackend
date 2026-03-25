import os
import jwt
import bcrypt
import sqlite3
import random

from datetime import datetime, timedelta
from fastapi import HTTPException, Header
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart



EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY        = os.getenv("JWT_SECRET", "baby_parenting_secret_key_change_in_production")
ALGORITHM         = "HS256"
TOKEN_EXPIRY_DAYS = 30
DB_PATH           = "users.db"



# ── Database setup ────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            email    TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            name     TEXT    DEFAULT '',
            verified INTEGER DEFAULT 0,
            created  TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT    NOT NULL,
            otp        TEXT    NOT NULL,
            purpose    TEXT    NOT NULL,
            expires_at TEXT    NOT NULL,
            used       INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── Request models ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:    str
    password: str
    name:     str = ""

class LoginRequest(BaseModel):
    email:    str
    password: str

class OtpVerifyRequest(BaseModel):
    email:   str
    otp:     str
    purpose: str

class SendOtpRequest(BaseModel):
    email:   str
    purpose: str

# ── Helpers ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: int, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email":   email,
        "exp":     datetime.utcnow() + timedelta(days=TOKEN_EXPIRY_DAYS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

# Email sender via SMTP

def send_otp_email(to_email: str, otp: str, purpose: str) -> bool:
    try:
        # ✅ YAHAN ADD KAR
        if not EMAIL_USER or not EMAIL_PASS:
            print("❌ Email credentials missing")
            return False
        print(f"📧 Sending OTP to {to_email} via SMTP")

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 30px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <span style="font-size: 42px;">👶</span>
                <h2 style="color: #2D1B0E; margin: 8px 0;">Baby Parenting Companion</h2>
            </div>
            <div style="background: linear-gradient(135deg, #FF8B94, #FFB06A);
                        border-radius: 16px; padding: 28px; text-align: center;">
                <p style="color: white; font-size: 15px; margin: 0 0 16px 0;">
                    {"Create your account" if purpose == "signup" else "Login to your account"}
                </p>
                <div style="background: white; border-radius: 12px;
                            padding: 16px 32px; display: inline-block; margin-bottom: 12px;">
                    <span style="font-size: 38px; font-weight: bold;
                                 color: #FF8B94; letter-spacing: 10px;">
                        {otp}
                    </span>
                </div>
                <p style="color: white; font-size: 12px; margin: 0; opacity: 0.9;">
                    This OTP expires in 10 minutes
                </p>
            </div>
            <p style="color: #AA8877; font-size: 11px; text-align: center; margin-top: 20px;">
                If you did not request this, please ignore this email.
            </p>
        </div>
        """

        # ✅ SMTP CODE (correct indentation)
        msg = MIMEMultipart()
        msg["From"] = f"Baby Parenting App <{EMAIL_USER}>"
        msg["To"] = to_email
        msg["Subject"] = "Your Baby Parenting OTP"

        msg.attach(MIMEText(html_body, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)

        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()

        print(f"✅ OTP sent successfully to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send OTP email to {to_email}: {e}")
        return False


# ── OTP endpoints ─────────────────────────────────────────────────────────────

def send_otp(req: SendOtpRequest) -> dict:
    email   = req.email.lower().strip()
    purpose = req.purpose

    if purpose == "signup":
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT id FROM users WHERE email = ?", (email,))
        exists = cursor.fetchone()
        conn.close()
        if exists:
            raise HTTPException(status_code=409, detail="Email already registered. Please login.")

    if purpose == "login":
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT id FROM users WHERE email = ?", (email,))
        exists = cursor.fetchone()
        conn.close()
        if not exists:
            raise HTTPException(status_code=404, detail="Email not found. Please register first.")

    otp        = generate_otp()
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM otps WHERE email = ? AND purpose = ?", (email, purpose))
    conn.execute(
        "INSERT INTO otps (email, otp, purpose, expires_at) VALUES (?, ?, ?, ?)",
        (email, otp, purpose, expires_at)
    )
    conn.commit()
    conn.close()

    sent = send_otp_email(email, otp, purpose)
    if not sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send OTP email. Please try again."
        )

    return {"success": True, "message": f"OTP sent to {email}. Check your inbox."}


def verify_otp(req: OtpVerifyRequest) -> dict:
    email   = req.email.lower().strip()
    otp     = req.otp.strip()
    purpose = req.purpose

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, otp, expires_at, used FROM otps WHERE email = ? AND purpose = ? ORDER BY id DESC LIMIT 1",
        (email, purpose)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")

    otp_id, saved_otp, expires_at, used = row

    if used:
        conn.close()
        raise HTTPException(status_code=400, detail="OTP already used. Please request a new one.")

    if datetime.utcnow() > datetime.fromisoformat(expires_at):
        conn.close()
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

    if otp != saved_otp:
        conn.close()
        raise HTTPException(status_code=400, detail="Incorrect OTP. Please try again.")

    conn.execute("UPDATE otps SET used = 1 WHERE id = ?", (otp_id,))
    conn.commit()
    conn.close()

    return {"success": True, "verified": True, "email": email}


def register_user(req: RegisterRequest) -> dict:
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    try:
        conn    = sqlite3.connect(DB_PATH)
        hashed  = hash_password(req.password)
        cursor  = conn.execute(
            "INSERT INTO users (email, password, name, verified) VALUES (?, ?, ?, 1)",
            (req.email.lower().strip(), hashed, req.name.strip())
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        token = create_token(user_id, req.email)
        return {
            "success": True,
            "token":   token,
            "email":   req.email,
            "name":    req.name,
            "message": "Account created successfully!"
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered. Please login.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def login_user(req: LoginRequest) -> dict:
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "SELECT id, email, password, name FROM users WHERE email = ?",
            (req.email.lower().strip(),)
        )
        user = cursor.fetchone()
        conn.close()
        if not user:
            raise HTTPException(status_code=401, detail="Email not found. Please register first.")
        user_id, email, hashed_pwd, name = user
        if not check_password(req.password, hashed_pwd):
            raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
        token = create_token(user_id, email)
        return {
            "success": True,
            "token":   token,
            "email":   email,
            "name":    name,
            "message": "Login successful!"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_me(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header.")
    token   = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    return {"success": True, "user_id": payload["user_id"], "email": payload["email"]}