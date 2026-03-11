from fastapi import FastAPI
from pydantic import BaseModel
from predictor import predict
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Parenting AI API",
    description="API for baby development and parenting guidance",
    version="1.0"
)

# Enable CORS for Android
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


@app.get("/")
def home():
    return {"message": "Parenting AI API Running"}


@app.post("/predict")
def run_prediction(data: RequestData):

    result = predict(data.model, data.text)

    if "error" in result:
        return result

    return {
        "domain": result.get("domain"),
        "title": result.get("skill_name"),
        "goal": result.get("parent_learning_goal"),
        "why": result.get("why_it_matters"),
        "how": result.get("how_to_teach"),
        "dos": result.get("parent_dos"),
        "donts": result.get("parent_donts"),
        "tip": result.get("parent_tip"),
        "steps": result.get("steps")
    }