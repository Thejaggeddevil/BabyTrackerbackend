from fastapi import FastAPI
from pydantic import BaseModel
from predictor import predict
from fastapi.middleware.cors import CORSMiddleware

from auth import (
    RegisterRequest, LoginRequest, SendOtpRequest, OtpVerifyRequest,
    register_user, login_user, get_me, send_otp, verify_otp
)

app = FastAPI(
    title="Parenting AI API",
    description="API for baby development and parenting guidance",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestData(BaseModel):
    model: str
    text: str


# ── Existing endpoints ────────────────────────────────────────────────────────

@app.get("/")
def home():
    return {"message": "Parenting AI API Running", "version": "2.0"}


@app.get("/models")
def list_models():
    """Returns all available model names — useful for debugging from Android."""
    from predictor import datasets
    return {"available_models": list(datasets.keys())}


@app.post("/predict")
def run_prediction(data: RequestData):
    result = predict(data.model, data.text)

    if "error" in result:
        return result

    steps = []
    goal  = result.get("parent_learning_goal") or result.get("goal") or ""
    how   = result.get("how_to_teach") or result.get("activity") or result.get("activity_idea") or ""
    tip   = result.get("parent_tip") or ""
    why   = result.get("why_it_matters") or ""
    sol   = result.get("solution_steps") or ""

    if sol:
        import ast
        try:
            parsed = ast.literal_eval(sol)
            if isinstance(parsed, list):
                steps = [str(s).strip() for s in parsed if str(s).strip()]
        except Exception:
            steps = [s.strip() for s in sol.split(".") if s.strip()]
    else:
        if goal:
            steps.append(f"Step 1 — Understand the goal: {goal}")
        if how:
            steps.append(f"Step 2 — What to do: {how}")
        if tip:
            steps.append(f"Step 3 — Keep in mind: {tip}")
        elif why:
            steps.append(f"Step 3 — Why this matters: {why}")

    return {
        "domain": (
            result.get("domain") or
            result.get("subject") or
            result.get("environment") or
            ""
        ),
        "title": (
            result.get("skill_name") or
            result.get("activity") or
            result.get("topic") or
            result.get("skill") or
            ""
        ),
        "goal": (
            result.get("parent_learning_goal") or
            result.get("goal") or
            result.get("learning_goal") or
            result.get("development_goal") or
            ""
        ),
        "why": (
            result.get("why_it_matters") or
            result.get("response_guidance") or
            result.get("learning_goal") or
            ""
        ),
        "how": (
            result.get("how_to_teach") or
            result.get("activity_idea") or
            result.get("activity") or
            result.get("trusted_action") or
            ""
        ),
        "dos":    _parse_list(result.get("parent_dos") or ""),
        "donts":  _parse_list(result.get("parent_donts") or ""),
        "tip": (
            result.get("parent_tip") or
            result.get("feedback_example") or
            result.get("emotional_tone") or
            ""
        ),
        "steps":      steps,
        "difficulty": result.get("difficulty_level") or "",
        "materials":  result.get("materials_needed") or "",
        "duration":   result.get("duration_minutes") or "",
        "example":    result.get("input") or result.get("example_prompt") or "",
        "answer":     result.get("output") or result.get("expected_response") or "",
        "scenario":   result.get("scenario") or "",
        "language":   result.get("language") or "",
    }


def _parse_list(raw: str) -> list:
    """Convert stringified Python list like "['a', 'b']" to actual list."""
    if not raw:
        return []
    import ast
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in raw.split(",") if x.strip()]


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/send-otp")
def send_otp_endpoint(req: SendOtpRequest):
    """Step 1 — Send OTP to email"""
    return send_otp(req)


@app.post("/verify-otp")
def verify_otp_endpoint(req: OtpVerifyRequest):
    """Step 2 — Verify OTP entered by user"""
    return verify_otp(req)


@app.post("/register")
def register(req: RegisterRequest):
    """Step 3 (signup) — Create account after OTP verified"""
    return register_user(req)


@app.post("/login")
def login(req: LoginRequest):
    """Step 3 (login) — Login after OTP verified"""
    return login_user(req)


@app.get("/me")
def me(authorization: str = None):
    return get_me(authorization)