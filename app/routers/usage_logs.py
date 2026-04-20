from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import UsageLog, User
from app.schemas.usage_log import UsageLogResponse
from app.services.openai_service import extract_text_from_image, simplify_text

router = APIRouter(prefix="/usage-logs", tags=["usage-logs"])

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}


@router.post("", response_model=UsageLogResponse, status_code=status.HTTP_201_CREATED)
async def create_usage_log(
    title: str = Form(..., min_length=1, max_length=200),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageLog:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"지원하지 않는 파일 형식입니다: {file.content_type}",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 파일은 업로드할 수 없습니다.",
        )

    try:
        extracted = extract_text_from_image(image_bytes, file.content_type)
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
