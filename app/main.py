from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.enums import PrivateQuestion
from app.routers import auth, usage_logs


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="BIF-OCR API",
    description="경계선 지능 아동을 위한 OCR 기반 텍스트 변환 서비스 백엔드",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(usage_logs.router)


PRIVATE_QUESTION_LABELS: dict[PrivateQuestion, str] = {
    PrivateQuestion.FAVORITE_FRUIT: "가장 좋아하는 과일의 이름은?",
    PrivateQuestion.BEST_FRIEND: "가장 절친한 친구의 이름은?",
    PrivateQuestion.FIRST_PET: "처음 키운 반려동물의 이름은?",
    PrivateQuestion.FAVORITE_TEACHER: "가장 존경하는 선생님의 이름은?",
    PrivateQuestion.BIRTH_CITY: "태어난 도시는?",
}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/private-questions", tags=["meta"])
def list_private_questions() -> list[dict[str, str]]:
    return [{"value": q.value, "label": label} for q, label in PRIVATE_QUESTION_LABELS.items()]
