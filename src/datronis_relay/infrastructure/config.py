from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TelegramConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = True
    bot_token: SecretStr


class SlackConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    # Bot User OAuth Token — starts with "xoxb-"
    bot_token: SecretStr = SecretStr("")
    # App-Level Token with connections:write — starts with "xapp-"
    app_token: SecretStr = SecretStr("")


class ClaudeConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model: str = "claude-sonnet-4-6"
    max_turns: int = Field(default=10, ge=1, le=100)


class StorageConfig(BaseModel):
    sqlite_path: str = "./data/relay.db"


class LoggingConfig(BaseModel):
    # `json` is the user-facing YAML key; `json_output` is the Python
    # attribute name because `json` would shadow pydantic's BaseModel.json()
    # method.
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())
    level: str = "INFO"
    json_output: bool = Field(default=True, alias="json")


class MetricsConfig(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=9464, ge=1, le=65535)


class SchedulerConfig(BaseModel):
    enabled: bool = True
    poll_interval_seconds: float = Field(default=30.0, ge=1.0, le=3600.0)
    max_tasks_per_user: int = Field(default=50, ge=1, le=10_000)
    batch_limit: int = Field(default=10, ge=1, le=100)


class AttachmentsConfig(BaseModel):
    enabled: bool = True
    max_bytes_per_file: int = Field(default=10 * 1024 * 1024, ge=1024)
    temp_dir: str = "./data/attachments"


class RateLimitConfig(BaseModel):
    per_minute: int = Field(default=20, ge=1)
    per_day: int = Field(default=1000, ge=1)


class UserConfig(BaseModel):
    id: str = Field(..., min_length=3)
    display_name: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)


class ModelPricingEntry(BaseModel):
    input_usd_per_mtok: float = Field(ge=0)
    output_usd_per_mtok: float = Field(ge=0)


class CostConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pricing: dict[str, ModelPricingEntry] = Field(default_factory=dict)


class AppConfig(BaseModel):
    """Root config model, loaded from YAML with optional env overrides.

    Env vars overriding secrets:
      - `DATRONIS_TELEGRAM_BOT_TOKEN`
    Env vars overriding non-secrets (optional):
      - `DATRONIS_CONFIG_PATH` — path to the YAML file (default: ./config.yaml)
      - `DATRONIS_LOG_LEVEL`, `DATRONIS_LOG_JSON` (honoured if set)
    """

    telegram: TelegramConfig
    slack: SlackConfig = Field(default_factory=SlackConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    attachments: AttachmentsConfig = Field(default_factory=AttachmentsConfig)
    users: list[UserConfig] = Field(..., min_length=1)
    cost: CostConfig = Field(default_factory=CostConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppConfig:
        resolved: str | Path = (
            path if path is not None else os.getenv("DATRONIS_CONFIG_PATH", "./config.yaml")
        )
        config_path = Path(resolved)
        if not config_path.exists():
            raise FileNotFoundError(
                f"config file not found: {config_path} "
                f"(set DATRONIS_CONFIG_PATH or create ./config.yaml — "
                f"see config.example.yaml)"
            )
        raw = yaml.safe_load(config_path.read_text()) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"config root must be a mapping, got {type(raw).__name__}")
        merged = _apply_env_overrides(raw)
        return cls.model_validate(merged)


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Allow critical fields to be overridden by env vars.

    Secrets should be injected this way — keeping them out of the YAML
    file makes it safe to commit `config.yaml` to a private repo or a
    configuration-management tool.
    """
    token = os.getenv("DATRONIS_TELEGRAM_BOT_TOKEN")
    if token:
        telegram = raw.setdefault("telegram", {})
        if isinstance(telegram, dict):
            telegram["bot_token"] = token

    slack_bot = os.getenv("DATRONIS_SLACK_BOT_TOKEN")
    if slack_bot:
        slack = raw.setdefault("slack", {})
        if isinstance(slack, dict):
            slack["bot_token"] = slack_bot
            slack.setdefault("enabled", True)

    slack_app = os.getenv("DATRONIS_SLACK_APP_TOKEN")
    if slack_app:
        slack = raw.setdefault("slack", {})
        if isinstance(slack, dict):
            slack["app_token"] = slack_app
            slack.setdefault("enabled", True)

    log_level = os.getenv("DATRONIS_LOG_LEVEL")
    if log_level:
        logging_ = raw.setdefault("logging", {})
        if isinstance(logging_, dict):
            logging_["level"] = log_level

    log_json = os.getenv("DATRONIS_LOG_JSON")
    if log_json is not None:
        logging_ = raw.setdefault("logging", {})
        if isinstance(logging_, dict):
            logging_["json"] = log_json.lower() in ("true", "1", "yes", "on")

    return raw
