from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (PROJECT_ROOT / ".env", Path(".env"))


class Settings(BaseSettings):
    app_name: str = "AI Copilot System"
    environment: str = Field(default="dev", alias="ENV")
    public_api_url: str = Field(default="http://localhost:8000", alias="PUBLIC_API_URL")
    cors_origins: str | None = Field(default=None, alias="CORS_ORIGINS")
    data_dir: Path = Field(default=Path("data"), alias="DATA_DIR")
    sqlite_path: Path = Field(default=Path("data/copilot.sqlite3"), alias="SQLITE_PATH")
    storage_backend: str | None = Field(default=None, alias="STORAGE_BACKEND")
    postgres_dsn: str | None = Field(default=None, alias="POSTGRES_DSN")

    chroma_collection: str = Field(default="knowledge_base", alias="CHROMA_COLLECTION")

    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_chat_model: str | None = Field(default=None, alias="OPENROUTER_CHAT_MODEL")
    openrouter_chat_fallback_models: str | None = Field(
        default=None,
        alias="OPENROUTER_CHAT_FALLBACK_MODELS",
    )
    openrouter_embedding_model: str | None = Field(
        default=None,
        alias="OPENROUTER_EMBEDDING_MODEL",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_app_title: str = Field(
        default="AI Copilot Local Console",
        alias="OPENROUTER_APP_TITLE",
    )
    openrouter_http_referer: str = Field(
        default="http://localhost:5173",
        alias="OPENROUTER_HTTP_REFERER",
    )

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_chat_model: str | None = Field(
        default="gemini-2.5-flash-lite",
        alias="GEMINI_CHAT_MODEL",
    )
    gemini_embedding_model: str | None = Field(
        default="text-embedding-004",
        alias="GEMINI_EMBEDDING_MODEL",
    )
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        alias="GEMINI_BASE_URL",
    )

    request_timeout_seconds: float = 45.0
    llm_temperature: float = 0.2
    price_per_1k_tokens: float = Field(default=0.0, alias="PRICE_PER_1K_TOKENS")
    max_upload_mb: int = Field(default=15, alias="MAX_UPLOAD_MB")
    retrieval_top_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 150

    clerk_jwks_url: str | None = Field(default=None, alias="CLERK_JWKS_URL")
    clerk_issuer: str | None = Field(default=None, alias="CLERK_ISSUER")
    clerk_audience: str | None = Field(default=None, alias="CLERK_AUDIENCE")
    dev_account_id: str = Field(default="dev-local", alias="DEV_ACCOUNT_ID")
    auth_disabled: bool = Field(default=False, alias="AUTH_DISABLED")

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def max_upload_bytes(self) -> int:
        if self.max_upload_mb <= 0:
            return 0
        return int(self.max_upload_mb) * 1024 * 1024

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
