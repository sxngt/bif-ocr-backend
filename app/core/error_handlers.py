from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

FIELD_LABELS: dict[str, str] = {
    "username": "아이디",
    "password": "비밀번호",
    "private_question": "나만의 질문",
    "private_answer": "나만의 질문 응답",
    "title": "제목",
    "file": "파일",
}

ENGLISH_DETAIL_KO: dict[str, str] = {
    "Not authenticated": "인증에 필요한 토큰이 없습니다.",
    "Not Found": "요청한 경로를 찾을 수 없습니다.",
    "Method Not Allowed": "허용되지 않은 메서드입니다.",
    "Internal Server Error": "서버 내부 오류가 발생했습니다.",
}


def _label(loc: tuple) -> str:
    for part in reversed(loc):
        if isinstance(part, str) and part not in {"body", "query", "path", "header", "cookie"}:
            return FIELD_LABELS.get(part, part)
    return "입력값"


def _format_validation_error(err: dict) -> str:
    label = _label(tuple(err.get("loc", ())))
    err_type = err.get("type", "")
    ctx = err.get("ctx") or {}

    if err_type == "missing":
        return f"{label} 값이 필요합니다."
    if err_type in {"string_too_short", "value_error.any_str.min_length"}:
        n = ctx.get("min_length")
        return f"{label} 은(는) 최소 {n}자 이상이어야 합니다." if n else f"{label} 길이가 너무 짧습니다."
    if err_type in {"string_too_long", "value_error.any_str.max_length"}:
        n = ctx.get("max_length")
        return f"{label} 은(는) 최대 {n}자까지 가능합니다." if n else f"{label} 길이가 너무 깁니다."
    if err_type == "string_type":
        return f"{label} 은(는) 문자열이어야 합니다."
    if err_type in {"int_parsing", "int_type"}:
        return f"{label} 은(는) 정수여야 합니다."
    if err_type in {"bool_parsing", "bool_type"}:
        return f"{label} 은(는) true/false 여야 합니다."
    if err_type == "enum":
        allowed = ctx.get("expected")
        return f"{label} 값이 허용 목록에 없습니다: {allowed}" if allowed else f"{label} 값이 올바르지 않습니다."
    if err_type.startswith("value_error"):
        return f"{label} 입력값이 올바르지 않습니다."
    if err_type == "json_invalid":
        return "요청 본문 JSON 형식이 올바르지 않습니다."
    return f"{label} 입력값이 올바르지 않습니다."


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    detail = _format_validation_error(errors[0]) if errors else "요청 형식이 올바르지 않습니다."
    return JSONResponse(status_code=422, content={"detail": detail})


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, str):
        detail = ENGLISH_DETAIL_KO.get(detail, detail)
    else:
        detail = "요청을 처리할 수 없습니다."
    headers = getattr(exc, "headers", None)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=headers)
