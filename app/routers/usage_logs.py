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

router = APIRouter(prefix="/usage-logs", tags=["usage-logs"])

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
PDF_TYPES = {"application/pdf"}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | PDF_TYPES


@router.post("", response_model=UsageLogResponse, status_code=status.HTTP_201_CREATED)
async def create_usage_log(
    title: str = Form(..., min_length=1, max_length=200),
    file: UploadFile = File(...),
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


@router.get("", response_model=list[UsageLogListItem])
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


@router.get("/{log_id}", response_model=UsageLogResponse)
def get_usage_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageLog:
    log = db.get(UsageLog, log_id)
    if log is None or log.is_deleted or log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
    return log


@router.patch("/{log_id}", response_model=UsageLogResponse)
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


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
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
