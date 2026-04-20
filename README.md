# BIF-OCR Backend

경계선 지능 아동을 위한 OCR 기반 텍스트 변환 서비스 백엔드.
FastAPI + SQLite + SQLAlchemy + OpenAI API.

강민서 인턴의 캡스톤 디자인 개발환경 지원을 위한 PoC 백엔드.

## 배포 환경 (Dev)

| 항목 | 값 |
|------|------|
| Base URL | `http://15.164.30.134:13001` |
| Swagger UI | http://15.164.30.134:13001/docs |
| Redoc | http://15.164.30.134:13001/redoc |
| OpenAPI JSON | http://15.164.30.134:13001/openapi.json |
| Health | http://15.164.30.134:13001/health |

프런트엔드 `.env` 예시:

```env
VITE_API_BASE_URL=http://15.164.30.134:13001
```

> 현재 HTTP 로 노출되어 있어 HTTPS 페이지에서는 Mixed Content 차단이 발생할 수 있습니다. 프런트도 HTTP 로 띄우거나, 이후 ALB + ACM 으로 HTTPS 전환을 검토하세요.

## 요구 사항

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- OpenAI API Key

## 시작하기

```bash
# 1) 의존성 설치
uv sync

# 2) 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 등 설정

# 3) (선택) DB 초기화 — 앱 시작 시 자동 생성되지만 수동으로도 가능
uv run python -m scripts.init_db

# 4-a) 개발 서버 실행 (자동 리로드, 포트 13001)
./scripts/run.sh

# 4-b) 배포용 실행 (워커 다중, --no-dev 의존성)
./scripts/deploy.sh
# 환경 변수로 조정 가능:
#   HOST=0.0.0.0 PORT=13001 WORKERS=4 LOG_LEVEL=info ./scripts/deploy.sh
```

로컬 Swagger UI: http://localhost:13001/docs (배포된 개발 서버는 위 **배포 환경 (Dev)** 섹션 참고)

## API 개요

### Auth
| Method | Path | 설명 |
|--------|------|------|
| POST | `/auth/signup` | 회원가입 (username, password, private_question, private_answer) |
| POST | `/auth/login` | 로그인 (3-factor: username + password + private_answer) → JWT |
| GET  | `/auth/me` | 현재 로그인 유저 정보 |

### Usage Logs
| Method | Path | 설명 |
|--------|------|------|
| POST   | `/usage-logs` | 이미지/PDF 업로드 → OCR → 단순화 → 저장 (multipart: `title`, `file`) |
| GET    | `/usage-logs` | 내 기록 목록 (soft-delete 제외, 최신순) |
| GET    | `/usage-logs/{id}` | 기록 상세 |
| PATCH  | `/usage-logs/{id}` | 제목 수정 |
| DELETE | `/usage-logs/{id}` | Soft delete |

### Meta
| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 |
| GET | `/private-questions` | 나만의 질문 Enum 목록 (프론트 렌더링용 label 포함) |

## 구조

```
app/
├── main.py             # FastAPI 엔트리포인트
├── config.py           # pydantic-settings 기반 설정
├── database.py         # SQLAlchemy 엔진/세션
├── enums.py            # PrivateQuestion Enum
├── core/
│   ├── security.py     # 비밀번호 해시 + JWT
│   └── deps.py         # get_current_user
├── models/             # User, UsageLog ORM
├── schemas/            # Pydantic DTO
├── routers/
│   ├── auth.py         # /auth/*
│   └── usage_logs.py   # /usage-logs/*
└── services/
    └── openai_service.py  # OCR + 텍스트 단순화
```

## 구현 메모

- **OCR**: OpenAI Vision (`gpt-4o` 등) 멀티모달 입력.
  - 이미지(`image/png|jpeg|webp|gif`)는 그대로 OCR.
  - PDF는 `pypdfium2` 로 페이지별 PNG 렌더링(기본 2배 스케일) 후 페이지별 OCR → 이어 붙임.
  - 비용/시간 보호용으로 **최대 20페이지**까지만 처리 (`PDF_PAGE_LIMIT`).
- **단순화**: `gpt-4o-mini` 기본. BIF 아동을 위한 프롬프트로 짧은 문장 + 마크다운 구조화.
- **인증**: 3-factor (username + password + private_answer). PRD 6.2 준수.
- **Soft Delete**: `is_deleted` 플래그. DELETE 엔드포인트는 flag만 변경.
- **S3**: PRD에서 Pending 상태이므로 `s3_key` 필드만 nullable로 준비, 실제 업로드 로직은 미구현.
