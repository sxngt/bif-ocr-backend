from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import UsageLog, User
from app.schemas.usage_log import UsageLogListItem, UsageLogResponse, UsageLogUpdate
from app.services.openai_service import (
    extract_text_from_image,
    extract_text_from_pdf,
    simplify_text,
)

router = APIRouter(prefix="/usage-logs", tags=["사용 기록"])

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
PDF_TYPES = {"application/pdf"}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | PDF_TYPES


@router.post(
    "",
    response_model=UsageLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="이미지/PDF 업로드 → OCR → 단순화 → 저장 (핵심 기능)",
    description=(
        "유저가 올린 **이미지** 또는 **PDF** 에서 텍스트를 추출(OCR)한 뒤, "
        "BIF 아동용 프롬프트로 **쉬운 문장(마크다운)** 으로 변환해 DB 에 저장한다.\n\n"
        "### 요청 형식\n"
        "`multipart/form-data` 로 아래 두 필드를 함께 전송한다.\n\n"
        "| 필드 | 타입 | 설명 |\n"
        "|------|------|------|\n"
        "| `title` | string | 기록 제목. 목록에서의 식별용 (1~200자). |\n"
        "| `file`  | file   | 이미지(png/jpeg/webp/gif) 또는 PDF (`application/pdf`). |\n\n"
        "### 처리 흐름\n"
        "1. `content-type` 검사 → 허용 형식이 아니면 **415**\n"
        "2. 파일이 비어 있으면 **400**\n"
        "3. OCR 수행\n"
        "   - 이미지: OpenAI Vision 에 그대로 전달\n"
        "   - PDF: `pypdfium2` 로 페이지별 PNG 렌더링 후 페이지마다 OCR → `## [페이지 N]` 헤더로 연결 "
        "(비용 보호용 **최대 20페이지** 상한)\n"
        "4. 추출된 원문을 쉬운 문장 프롬프트로 단순화 → 마크다운 결과 생성\n"
        "5. DB 저장 후 상세 응답 반환\n\n"
        "### 소요 시간\n"
        "한 페이지당 수 초 단위. PDF 페이지 수가 많으면 수십 초 이상 걸릴 수 있다.\n"
        "프런트엔드는 업로드 버튼을 누른 뒤 로딩 스피너와 '이 작업은 시간이 걸려요' 안내를 노출하자."
    ),
    responses={
        201: {"description": "저장된 기록 상세 (UsageLogResponse)."},
        400: {
            "description": "빈 파일",
            "content": {"application/json": {"example": {"detail": "빈 파일은 업로드할 수 없습니다."}}},
        },
        401: {"description": "토큰 누락/만료/변조"},
        415: {
            "description": "지원하지 않는 파일 형식",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "지원하지 않는 파일 형식입니다: text/plain (이미지 또는 application/pdf 만 허용)"
                    }
                }
            },
        },
        422: {
            "description": "OCR 결과가 비어 있음 (이미지에 글자가 없거나 품질이 너무 낮은 경우)",
            "content": {
                "application/json": {
                    "example": {"detail": "이미지에서 텍스트를 추출하지 못했습니다."}
                }
            },
        },
        502: {
            "description": "OpenAI 호출 실패",
            "content": {
                "application/json": {
                    "example": {"detail": "OCR 처리 중 오류가 발생했습니다: ..."}
                }
            },
        },
    },
)
async def create_usage_log(
    title: str = Form(
        ...,
        min_length=1,
        max_length=200,
        description="기록 제목 (1~200자).",
        examples=["국어 교과서 3단원"],
    ),
    file: UploadFile = File(
        ...,
        description=(
            "업로드할 원본 파일. 허용 타입: "
            "`image/png`, `image/jpeg`, `image/webp`, `image/gif`, `application/pdf`."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageLog:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"지원하지 않는 파일 형식입니다: {file.content_type} "
            "(이미지 또는 application/pdf 만 허용)",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 파일은 업로드할 수 없습니다.",
        )

    try:
        if file.content_type in PDF_TYPES:
            extracted = extract_text_from_pdf(file_bytes)
        else:
            extracted = extract_text_from_image(file_bytes, file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OCR 처리 중 오류가 발생했습니다: {e}",
        ) from e

    if not extracted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="이미지에서 텍스트를 추출하지 못했습니다.",
        )

    try:
        simplified = simplify_text(extracted)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"텍스트 단순화 중 오류가 발생했습니다: {e}",
        ) from e

    log = UsageLog(
        user_id=current_user.id,
        title=title,
        file_name=file.filename or "unknown",
        s3_key=None,
        compact_result=simplified,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get(
    "",
    response_model=list[UsageLogListItem],
    summary="내 기록 목록 (최신순)",
    description=(
        "현재 로그인한 유저의 사용 기록을 **최신순**으로 반환한다.\n\n"
        "- Soft-delete 된 기록(`is_deleted=true`)은 제외된다.\n"
        "- 페이로드 절약을 위해 본문(`compact_result`) 은 포함하지 않는다. 본문이 필요하면 상세 조회(`GET /usage-logs/{id}`)를 사용.\n"
        "- 다른 유저의 기록은 절대 노출되지 않는다."
    ),
    responses={
        200: {"description": "목록(빈 배열 가능)"},
        401: {"description": "토큰 누락/만료/변조"},
    },
)
def list_usage_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UsageLog]:
    stmt = (
        select(UsageLog)
        .where(UsageLog.user_id == current_user.id, UsageLog.is_deleted.is_(False))
        .order_by(desc(UsageLog.created_at))
    )
    return list(db.scalars(stmt).all())


@router.get(
    "/{log_id}",
    response_model=UsageLogResponse,
    summary="기록 상세 조회",
    description=(
        "특정 기록의 상세 정보를 반환한다. 단순화된 마크다운 본문(`compact_result`) 포함.\n\n"
        "- 본인 소유가 아니거나 soft-delete 된 기록은 **404** 로 응답 (존재 여부를 숨긴다)."
    ),
    responses={
        200: {"description": "기록 상세"},
        401: {"description": "토큰 누락/만료/변조"},
        404: {"description": "기록 없음 또는 권한 없음"},
    },
)
def get_usage_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageLog:
    log = db.get(UsageLog, log_id)
    if log is None or log.is_deleted or log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
    return log


@router.patch(
    "/{log_id}",
    response_model=UsageLogResponse,
    summary="기록 제목 수정",
    description=(
        "기록의 **제목만** 변경한다. 본문(`compact_result`) 은 재생성되지 않으며 수정 대상이 아니다.\n\n"
        "본인 소유가 아니거나 삭제된 기록은 404."
    ),
    responses={
        200: {"description": "수정된 기록 상세"},
        401: {"description": "토큰 누락/만료/변조"},
        404: {"description": "기록 없음 또는 권한 없음"},
        422: {"description": "제목 길이 검증 실패"},
    },
)
def update_usage_log(
    log_id: str,
    payload: UsageLogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageLog:
    log = db.get(UsageLog, log_id)
    if log is None or log.is_deleted or log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
    log.title = payload.title
    db.commit()
    db.refresh(log)
    return log


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="기록 삭제 (Soft delete)",
    description=(
        "기록을 **soft-delete** 한다 (실제 행 삭제가 아닌 `is_deleted=true` 플래그 변경).\n\n"
        "- 목록/상세 API 에서는 더 이상 조회되지 않지만 DB 에는 보존된다.\n"
        "- 동일 id 로 재시도하면 404 (이미 삭제된 것으로 간주)."
    ),
    responses={
        204: {"description": "삭제 성공. 응답 본문 없음."},
        401: {"description": "토큰 누락/만료/변조"},
        404: {"description": "기록 없음 또는 권한 없음"},
    },
)
def delete_usage_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    log = db.get(UsageLog, log_id)
    if log is None or log.is_deleted or log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
    log.is_deleted = True
    db.commit()
