from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # OpenAI
    openai_api_key: str = ""
    supervisor_llm: str = "gpt-4o"
    fast_llm: str = "gpt-4o-mini"

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "orthoassist-dev"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # Models
    hand_model_path: str = "models/hand_yolo.pt"
    leg_model_path: str = "models/leg_yolo.pt"

    # Detection thresholds
    router_threshold: float = 0.70
    detector_score_min: float = 0.35
    nms_iou: float = 0.50
    triage_red_threshold: float = 0.80
    triage_amber_threshold: float = 0.60

    # Storage
    storage_type: str = "local"
    storage_path: str = "./storage"
    cloudinary_url: str = ""

    # Security
    secret_key: str = "change-me"
    phi_redaction_enabled: bool = True
    medical_disclaimer_enabled: bool = True

    # LangGraph
    max_agent_iterations: int = 10
    session_ttl_seconds: int = 3600

    # MongoDB
    mongodb_uri: str = ""
    mongodb_db_name: str = "orthoassist"

    # API
    cors_allow_origins: str = "*"
    chat_request_timeout_seconds: int = 45

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def resolved_storage_path(self) -> Path:
        storage = Path(self.storage_path)
        if not storage.is_absolute():
            storage = self.project_root / storage
        return storage.resolve()

    @property
    def resolved_hand_model_path(self) -> Path:
        hand_model = Path(self.hand_model_path)
        if not hand_model.is_absolute():
            hand_model = self.project_root / hand_model
        return hand_model.resolve()

    @property
    def resolved_leg_model_path(self) -> Path:
        leg_model = Path(self.leg_model_path)
        if not leg_model.is_absolute():
            leg_model = self.project_root / leg_model
        return leg_model.resolve()

    @property
    def cors_origins(self) -> list[str]:
        origins = [value.strip() for value in self.cors_allow_origins.split(",") if value.strip()]
        return origins or ["*"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
