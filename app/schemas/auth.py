from pydantic import BaseModel, ConfigDict, Field

from app.enums import PrivateQuestion


class SignupRequest(BaseModel):
    """회원가입 요청 본문.

    3-factor 인증(아이디 + 비밀번호 + 나만의 질문 응답)에 필요한 계정을 만든다.
    `private_question` 은 고정된 Enum 값 중 하나만 허용한다.
    """

    username: str = Field(
        min_length=3,
        max_length=50,
        description=(
            "로그인에 사용할 **아이디**. 3~50자. 다른 유저와 중복 불가. "
            "중복 시 409 Conflict 응답."
        ),
        examples=["minsuh_kang"],
    )
    password: str = Field(
        min_length=6,
        max_length=100,
        description=(
            "평문 비밀번호. 서버에서 **bcrypt** 로 해시 저장되므로 원문은 DB 에 남지 않는다. "
            "6~100자."
        ),
        examples=["changeme123!"],
    )
    private_question: PrivateQuestion = Field(
        description=(
            "**나만의 질문(Enum).** 자유 문자열이 아니라 사전 정의된 코드만 허용.\n\n"
            "| Enum 값 | 프런트에 표시할 질문 |\n"
            "|---------|----------------------|\n"
            "| `FAVORITE_FRUIT` | 가장 좋아하는 과일의 이름은? |\n"
            "| `BEST_FRIEND` | 가장 절친한 친구의 이름은? |\n"
            "| `FIRST_PET` | 처음 키운 반려동물의 이름은? |\n"
            "| `FAVORITE_TEACHER` | 가장 존경하는 선생님의 이름은? |\n"
            "| `BIRTH_CITY` | 태어난 도시는? |\n\n"
            "프런트엔드는 `GET /private-questions` 로 위 매핑을 받아 드롭다운에 렌더링한다."
        ),
        examples=["BEST_FRIEND"],
    )
    private_answer: str = Field(
        min_length=1,
        max_length=100,
        description=(
            "위 질문에 대한 **응답 문자열**. 1~100자. 로그인 시 3번째 자격 증명으로 사용됨. "
            "서버는 비교 시 문자열 양끝 공백만 trim 한다 (대소문자 구분)."
        ),
        examples=["김근영"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "minsuh_kang",
                "password": "changeme123!",
                "private_question": "BEST_FRIEND",
                "private_answer": "김근영",
            }
        }
    )


class LoginRequest(BaseModel):
    """로그인 요청 (3-factor).

    `username` + `password` + `private_answer` **모두 일치해야** 성공한다.
    어느 하나라도 틀리면 어떤 값이 틀렸는지 구분 없이 401 을 반환한다(계정 탐색 방어).
    """

    username: str = Field(
        description="가입 시 등록한 아이디.",
        examples=["minsuh_kang"],
    )
    password: str = Field(
        description="가입 시 등록한 평문 비밀번호.",
        examples=["changeme123!"],
    )
    private_answer: str = Field(
        description=(
            "유저가 선택한 나만의 질문에 대한 응답. "
            "프런트엔드는 유저에게 본인의 질문을 직접 기억하게 하거나, "
            "로그인 폼에서 드롭다운으로 질문을 함께 노출해 사용자가 스스로 선택하게 해도 된다."
        ),
        examples=["김근영"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "minsuh_kang",
                "password": "changeme123!",
                "private_answer": "김근영",
            }
        }
    )


class TokenResponse(BaseModel):
    """로그인 성공 응답.

    프런트엔드는 `access_token` 을 저장한 뒤, 보호된 엔드포인트를 호출할 때마다
    `Authorization: Bearer {access_token}` 헤더로 전달해야 한다.
    """

    access_token: str = Field(
        description=(
            "JWT(JSON Web Token). payload 에 `sub=user.id` 가 담겨 있다. "
            "기본 만료 60분 (`ACCESS_TOKEN_EXPIRE_MINUTES`)."
        ),
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ..."],
    )
    token_type: str = Field(
        default="bearer",
        description="항상 `bearer`. OAuth2 표준을 따른다.",
    )


class UserResponse(BaseModel):
    """유저 공개 정보. 비밀번호/나만의 질문 응답은 절대 노출되지 않는다."""

    id: str = Field(description="유저 UUID (PK).", examples=["4e2b5c6f-ab09-4f6c-8e53-0b3d7a2a1234"])
    username: str = Field(description="로그인 아이디.", examples=["minsuh_kang"])
    private_question: PrivateQuestion = Field(
        description=(
            "유저가 선택한 나만의 질문 Enum 값. "
            "프런트는 이 값을 받아 질문 텍스트로 렌더링한다."
        ),
    )

    model_config = ConfigDict(from_attributes=True)
