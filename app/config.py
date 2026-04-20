from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_ocr_model: str = "gpt-4o"
    openai_summary_model: str = "gpt-4o-mini"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    database_url: str = "sqlite:///./bif_ocr.db"

    app_env: str = "dev"


settings = Settings()
