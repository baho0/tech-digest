"""Runtime settings (.env / environment) and YAML config loading."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class SourceConfig(BaseModel):
    name: str
    type: str
    tier: int = 2
    weight: float | None = None  # overrides the tier weight in scoring
    url: str | None = None
    category_hint: str | None = None
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TD_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite:///data/techdigest.db"
    sources_file: Path = Path("config/sources.yaml")
    scoring_file: Path = Path("config/scoring.yaml")

    timezone: str = "Europe/Istanbul"
    lookback_hours: int = 24
    http_timeout: float = 20.0
    user_agent: str = "techdigest/0.1 (personal news digest)"

    # SMTP — Gmail today, self-hosted server later: only these values change.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_timeout: float = 30.0
    mail_from: str | None = None
    mail_to: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("mail_to", mode="before")
    @classmethod
    def _split_recipients(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [a.strip() for a in v.split(",") if a.strip()]
        return v

    @cached_property
    def sources(self) -> list[SourceConfig]:
        data = _load_yaml(self.sources_file)
        return [SourceConfig(**s) for s in data.get("sources", [])]

    @cached_property
    def scoring(self) -> dict[str, Any]:
        return _load_yaml(self.scoring_file)


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get_settings() -> Settings:
    return Settings()
