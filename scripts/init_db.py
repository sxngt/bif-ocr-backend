"""초기 DB 생성 스크립트. `uv run python -m scripts.init_db` 로 실행."""

from app.database import Base, engine
from app.models import UsageLog, User  # noqa: F401  (모델 등록 목적)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("DB 테이블 생성 완료.")


if __name__ == "__main__":
    main()
