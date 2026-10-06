"""Application configuration loaded from the environment and ``.env``.

A single ``Settings`` object holds every setting. Secrets use ``SecretStr`` so
they never appear in logs or trace metadata by accident. Each field's ``.env``
name is documented in ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read once from the environment or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # An OpenRouter model id, e.g. "openai/gpt-4o-mini". The Phase 1 default is a placeholder.
    scout_model: str = Field(default="openai/gpt-4o-mini", alias="SCOUT_MODEL")
    scout_tailor_model: str = Field(default="openai/gpt-4o-mini", alias="SCOUT_TAILOR_MODEL")

    openrouter_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENROUTER_API_KEY")
    llm_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="LLM_BASE_URL")

    # "local" = self-hosted Opik (needs OPIK_URL_OVERRIDE); "cloud" = Opik Cloud (needs OPIK_API_KEY).
    opik_mode: Literal["local", "cloud"] = Field(default="local", alias="OPIK_MODE")
    opik_url_override: str = Field(default="", alias="OPIK_URL_OVERRIDE")
    trace_attach_cv: bool = Field(default=False, alias="TRACE_ATTACH_CV")
    opik_api_key: SecretStr = Field(default=SecretStr(""), alias="OPIK_API_KEY")
    opik_workspace: str = Field(default="", alias="OPIK_WORKSPACE")
    opik_project_name: str = Field(default="job-scout", alias="OPIK_PROJECT_NAME")
    opik_enabled: bool = Field(default=True, alias="OPIK_ENABLED")

    jsearch_api_key: SecretStr = Field(default=SecretStr(""), alias="JSEARCH_API_KEY")
    adzuna_app_id: SecretStr = Field(default=SecretStr(""), alias="ADZUNA_APP_ID")
    adzuna_app_key: SecretStr = Field(default=SecretStr(""), alias="ADZUNA_APP_KEY")

    # Scheduled run (`job-scout run`) and notifications. Each channel is off until fully configured.
    scout_cv_path: str = Field(default="private/cv.pdf", alias="SCOUT_CV_PATH")
    scout_db_path: str = Field(default="private/scout.db", alias="SCOUT_DB_PATH")
    notify_min_score: int = Field(default=70, alias="NOTIFY_MIN_SCORE")
    search_plan_path: str = Field(default="config/search.csv", alias="SEARCH_PLAN_PATH")
    max_jobs_per_scan: int = Field(default=40, alias="MAX_JOBS_PER_SCAN")
    telegram_bot_token: SecretStr = Field(default=SecretStr(""), alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    telegram_thread_id: str = Field(default="", alias="TELEGRAM_THREAD_ID")
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: SecretStr = Field(default=SecretStr(""), alias="SMTP_PASSWORD")
    email_to: str = Field(default="", alias="EMAIL_TO")

    max_llm_calls_per_run: int = Field(default=25, alias="MAX_LLM_CALLS_PER_RUN")

    @field_validator(
        "opik_workspace",
        "opik_project_name",
        "opik_url_override",
        "telegram_chat_id",
        "telegram_thread_id",
        "smtp_user",
        "email_to",
        "scout_model",
        "scout_tailor_model",
        mode="before",
    )
    @classmethod
    def _drop_inline_comment(cls, value: object) -> object:
        """Treat a value that is only a ``# comment`` as empty.

        Guards the common ``.env`` mistake of leaving a key blank but keeping its
        trailing comment, which some parsers read as the value.
        """
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("#"):
                return ""
        return value

    @property
    def has_telegram(self) -> bool:
        """Whether Telegram notifications are configured."""
        return bool(self.telegram_bot_token.get_secret_value() and self.telegram_chat_id)

    @property
    def has_email(self) -> bool:
        """Whether email notifications are configured."""
        return bool(self.smtp_user and self.smtp_password.get_secret_value() and self.email_to)

    @property
    def has_jsearch(self) -> bool:
        """Whether a JSearch API key is configured."""
        return bool(self.jsearch_api_key.get_secret_value())

    @property
    def has_adzuna(self) -> bool:
        """Whether both Adzuna credentials are configured."""
        return bool(self.adzuna_app_id.get_secret_value() and self.adzuna_app_key.get_secret_value())

    @property
    def has_opik(self) -> bool:
        """Whether Opik tracing is enabled and the chosen mode has what it needs."""
        if not self.opik_enabled:
            return False
        if self.opik_mode == "local":
            return bool(self.opik_url_override)
        return bool(self.opik_api_key.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
