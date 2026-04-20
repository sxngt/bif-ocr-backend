from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UsageLogResponse(BaseModel):
    """사용 기록 **상세** 응답. OCR → 단순화된 본문(`compact_result`) 포함."""

    id: str = Field(
        description="기록 UUID. 상세 조회/수정/삭제 엔드포인트의 path param 으로 사용한다.",
        examples=["7a9d4f8c-bead-4b9a-9c2b-e0e8b0d3f111"],
    )
    title: str = Field(
        description="유저가 지정한 기록 제목. 목록 화면에서 식별용으로 쓰인다.",
        examples=["국어 교과서 3단원 요약"],
    )
    file_name: str = Field(
        description="업로드한 원본 파일명. 예: `교과서_3장.pdf`, `photo.jpg`.",
        examples=["교과서_3장.pdf"],
    )
    s3_key: str | None = Field(
        default=None,
        description=(
            "원본 파일을 S3 에 저장한 경우의 키. "
            "현재는 S3 도입이 **Pending** 이므로 항상 `null` 을 반환한다. (PRD 9.2 참고)"
        ),
    )
    compact_result: str = Field(
        description=(
            "OCR 로 추출한 원문을 BIF 아동용 프롬프트로 단순화한 **마크다운 문자열**.\n\n"
            "프런트엔드는 `react-markdown` 등 마크다운 렌더러로 출력하면 된다. "
            "PDF 업로드의 경우 페이지마다 `## [페이지 N]` 섹션이 붙는다."
        ),
        examples=[
            "## 이야기 줄거리\n\n- **주인공** 은 학교에 간다.\n- 친구를 만난다.\n- 함께 점심을 먹는다."
        ],
    )
    created_at: datetime = Field(description="생성 시각 (ISO8601, 서버 시간).")
    updated_at: datetime = Field(description="최종 수정 시각 (제목 변경 시 갱신).")

    model_config = ConfigDict(from_attributes=True)


class UsageLogListItem(BaseModel):
    """사용 기록 **목록** 아이템. 본문(`compact_result`) 은 포함하지 않는다 (페이로드 절약)."""

    id: str = Field(description="기록 UUID.")
    title: str = Field(description="기록 제목.")
    file_name: str = Field(description="원본 파일명.")
    created_at: datetime = Field(description="생성 시각.")

    model_config = ConfigDict(from_attributes=True)


class UsageLogUpdate(BaseModel):
    """기록 제목 수정 요청."""

    title: str = Field(
        min_length=1,
        max_length=200,
        description="새 제목. 1~200자.",
        examples=["국어 교과서 3단원 요약 (수정본)"],
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "국어 교과서 3단원 요약 (수정본)"}}
    )
