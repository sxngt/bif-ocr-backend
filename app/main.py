from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.enums import PrivateQuestion
from app.routers import auth, usage_logs

API_DESCRIPTION = """
## BIF-OCR 백엔드 API

경계선 지능 아동(Borderline Intellectual Functioning)을 위한 OCR 기반 텍스트 변환 서비스의 백엔드입니다.

강민서 인턴의 캡스톤 디자인 개발환경 지원을 위한 **PoC 백엔드** 입니다.

---

### 전체 플로우 (프런트엔드 연동 순서)

1. **회원가입** — `POST /auth/signup`
2. **로그인** — `POST /auth/login` → 응답의 `access_token` 저장
3. 이후 모든 보호 엔드포인트는 요청 헤더에 아래 추가
   ```
   Authorization: Bearer {access_token}
   ```
4. **파일 업로드 → 변환 결과 수신** — `POST /usage-logs` (`multipart/form-data`)
5. **목록/상세/삭제** — `GET /usage-logs`, `GET /usage-logs/{id}`, `DELETE /usage-logs/{id}`

Swagger UI 우측 상단 **Authorize** 버튼을 누르고 토큰을 입력하면 이 페이지에서 직접 보호 엔드포인트를 테스트할 수 있습니다.

---

### 인증 (3-factor)

| 자격 | 설명 |
|------|------|
| `username` | 아이디 |
| `password` | 비밀번호 (bcrypt 해시 저장) |
| `private_answer` | 유저가 선택한 "나만의 질문" 에 대한 응답 |

세 값이 모두 맞아야 로그인이 성공합니다. 하나라도 틀리면 동일한 401 을 반환합니다 (계정 탐색 방지).

나만의 질문 종류는 `GET /private-questions` 로 조회하세요.

---

### 공용 규약

- 모든 시간 필드는 ISO8601 형식(서버 시간).
- 모든 오류는 `{"detail": "사람이 읽을 수 있는 메시지"}` JSON 으로 응답.
- 페이지네이션 없음 (PoC 범위).
- 응답 body 가 없는 성공 응답은 `204 No Content`.

---

### 기술 스택

- **FastAPI** + **SQLAlchemy** (SQLite)
- **OpenAI Vision** (`gpt-4o`) 이미지 OCR
- **pypdfium2** PDF → 이미지 렌더링 후 페이지별 OCR
- **bcrypt** 비밀번호 해시, **JWT** 세션 토큰
"""

TAGS_METADATA = [
    {
        "name": "인증",
        "description": (
            "회원가입, 로그인(3-factor), 내 정보 조회. "
            "로그인에 성공하면 JWT 를 받아 이후 모든 보호 엔드포인트 호출 시 "
            "`Authorization: Bearer {access_token}` 헤더에 실어 보낸다."
        ),
    },
    {
        "name": "사용 기록",
        "description": (
            "**핵심 기능**. 이미지/PDF 를 올리면 OCR → 쉬운 문장 변환 → DB 저장까지 한 번에 수행한다. "
            "목록/상세/제목 수정/Soft Delete 를 제공한다."
        ),
    },
    {
        "name": "메타",
        "description": (
            "헬스체크, 나만의 질문 Enum 매핑 등 프런트 렌더링 보조용 엔드포인트. "
            "인증이 필요하지 않다."
        ),
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="BIF-OCR API",
    description=API_DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
    contact={"name": "강민서 (인턴)", "email": "sxngt.dev@gmail.com"},
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "list",
        "defaultModelsExpandDepth": 2,
        "tryItOutEnabled": True,
    },
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


@app.get(
    "/health",
    tags=["메타"],
    summary="헬스체크",
    description=(
        "서버가 살아 있는지 확인하는 단순 엔드포인트. "
        "로드밸런서/모니터링의 liveness check 용으로 쓸 수 있다."
    ),
    responses={200: {"content": {"application/json": {"example": {"status": "ok"}}}}},
)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/private-questions",
    tags=["메타"],
    summary="나만의 질문 목록",
    description=(
        "회원가입 화면의 **드롭다운** 에 렌더링할 Enum 값 ↔ 사람이 읽을 질문 매핑.\n\n"
        "프런트는 `value` 를 서버로 다시 보내고, 사용자에게는 `label` 을 보여준다."
    ),
    responses={
        200: {
            "description": "Enum 매핑 리스트",
            "content": {
                "application/json": {
                    "example": [
                        {"value": "FAVORITE_FRUIT", "label": "가장 좋아하는 과일의 이름은?"},
                        {"value": "BEST_FRIEND", "label": "가장 절친한 친구의 이름은?"},
                        {"value": "FIRST_PET", "label": "처음 키운 반려동물의 이름은?"},
                        {"value": "FAVORITE_TEACHER", "label": "가장 존경하는 선생님의 이름은?"},
                        {"value": "BIRTH_CITY", "label": "태어난 도시는?"},
                    ]
                }
            },
        }
    },
)
def list_private_questions() -> list[dict[str, str]]:
    return [{"value": q.value, "label": label} for q, label in PRIVATE_QUESTION_LABELS.items()]
