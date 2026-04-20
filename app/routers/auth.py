from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["인증"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description=(
        "새 유저 계정을 만든다.\n\n"
        "- **username** 은 시스템 전체에서 유일해야 한다. 중복이면 409 Conflict.\n"
        "- **password** 는 서버에서 bcrypt 로 해시된 후 저장되므로 원문은 보관되지 않는다.\n"
        "- **private_question / private_answer** 는 로그인 시 3번째 자격 증명으로 사용된다.\n\n"
        "성공 응답에는 비밀번호와 나만의 질문 응답이 포함되지 않는다."
    ),
    responses={
        201: {"description": "회원가입 성공. 생성된 유저 공개 정보를 반환."},
        409: {
            "description": "이미 사용 중인 아이디",
            "content": {
                "application/json": {"example": {"detail": "이미 사용 중인 아이디입니다."}}
            },
        },
        422: {"description": "입력값 검증 실패 (길이/형식 등)"},
    },
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> User:
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디입니다.",
        )

    user = User(
        username=payload.username,
        password=hash_password(payload.password),
        private_question=payload.private_question,
        private_answer=payload.private_answer,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인 (3-factor)",
    description=(
        "아이디 + 비밀번호 + 나만의 질문 응답을 모두 검증하고, 통과하면 JWT 를 발급한다.\n\n"
        "**프런트 사용법**\n"
        "1. 이 엔드포인트에 세 값을 POST\n"
        "2. 응답의 `access_token` 을 로컬 저장 (localStorage, 쿠키 등)\n"
        "3. 이후 모든 보호 엔드포인트 호출 시 `Authorization: Bearer {access_token}` 헤더 추가\n\n"
        "**보안 참고**: 어느 값이 틀렸는지는 의도적으로 구분하지 않고 모두 401 로 동일한 메시지를 반환한다 "
        "(username 존재 여부를 드러내지 않기 위함)."
    ),
    responses={
        200: {"description": "로그인 성공. JWT 발급."},
        401: {
            "description": "자격 증명 중 하나 이상 불일치",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "아이디/비밀번호/나만의 질문 응답 중 일치하지 않는 값이 있습니다."
                    }
                }
            },
        },
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="아이디/비밀번호/나만의 질문 응답 중 일치하지 않는 값이 있습니다.",
    )
    if user is None:
        raise invalid
    if not verify_password(payload.password, user.password):
        raise invalid
    if user.private_answer.strip() != payload.private_answer.strip():
        raise invalid

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="내 정보 조회",
    description=(
        "현재 로그인한 유저의 공개 정보를 반환한다.\n\n"
        "헤더에 유효한 `Authorization: Bearer {access_token}` 이 필요하다. "
        "토큰이 없거나 만료됐거나 변조되면 401 을 반환한다."
    ),
    responses={
        200: {"description": "유저 공개 정보"},
        401: {"description": "토큰 누락/만료/변조"},
    },
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
