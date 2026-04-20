import base64

from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


OCR_SYSTEM_PROMPT = (
    "당신은 정확한 OCR 엔진입니다. "
    "입력으로 주어진 이미지에서 보이는 모든 텍스트를 그대로 추출하세요. "
    "추출한 텍스트만 출력하며, 설명이나 요약을 덧붙이지 마세요. "
    "줄바꿈과 문단 구분은 원본과 유사하게 유지하세요."
)

SIMPLIFY_SYSTEM_PROMPT = (
    "당신은 경계선 지능 아동(Borderline Intellectual Functioning)을 위한 "
    "읽기 보조 도우미입니다. 다음 규칙을 반드시 지키세요.\n"
    "1. 어려운 단어는 쉬운 단어로 바꾸세요.\n"
    "2. 한 문장은 가능하면 짧게(20자 내외) 씁니다.\n"
    "3. 핵심만 남기고 불필요한 수식은 제거합니다.\n"
    "4. 글의 흐름이 잘 보이도록 마크다운 제목(##), 목록(-), 굵은 글씨를 사용합니다.\n"
    "5. 전문 용어가 나오면 괄호 안에 쉬운 설명을 덧붙입니다.\n"
    "6. 원문에 없는 내용을 지어내지 않습니다.\n"
    "출력은 마크다운 형식으로만 작성하세요."
)


def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
    """이미지에서 텍스트를 추출한다 (OCR)."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    response = _get_client().chat.completions.create(
        model=settings.openai_ocr_model,
        messages=[
            {"role": "system", "content": OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "이 이미지의 모든 텍스트를 추출해 주세요."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


def simplify_text(raw_text: str) -> str:
    """추출된 원문을 쉬운 문장(마크다운)으로 변환한다."""
    response = _get_client().chat.completions.create(
        model=settings.openai_summary_model,
        messages=[
            {"role": "system", "content": SIMPLIFY_SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 글을 쉽게 바꿔 주세요.\n\n---\n{raw_text}"},
        ],
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()
