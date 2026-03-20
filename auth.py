import os
import jwt
import bcrypt
import sqlite3
from datetime import datetime, timedelta
from fastapi import HTTPException, Header
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY  = os.getenv("JWT_SECRET", "baby_parenting_secret_key_change_in_production")
ALGORITHM   = "HS256"
TOKEN_EXPIRY_DAYS = 30
DB_PATH     = "users.db"

# ── Database setup ────────────────────────────────────────────────────────────

def init_db():
    """Create users table if not exists — runs once at startup."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            email    TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            name     TEXT    DEFAULT '',
            created  TEXT    DEFAULT CURRENT_TIMESTAMP
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
    """Returns payload if valid, raises HTTPException if not."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

# ── Auth endpoints — import these in main.py ─────────────────────────────────

def register_user(req: RegisterRequest) -> dict:
    """POST /register"""
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    try:
        conn = sqlite3.connect(DB_PATH)
        hashed = hash_password(req.password)
        cursor = conn.execute(
            "INSERT INTO users (email, password, name) VALUES (?, ?, ?)",
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
    """POST /login"""
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
    """GET /me — verify token and return user info"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header.")

    token   = authorization.replace("Bearer ", "")
    payload = verify_token(token)

    return {
        "success":  True,
        "user_id":  payload["user_id"],
        "email":    payload["email"]
    }