"""Tests for `main.py` — the composition-root builder functions and
`_run_until_stopped`. Real adapters are patched with stand-ins so no
network calls are made.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from datronis_relay import main as main_module
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.domain.messages import Platform
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.infrastructure.config import (
    AppConfig,
    AttachmentsConfig,
    ClaudeConfig,
    CostConfig,
    LoggingConfig,
    MetricsConfig,
    ModelPricingEntry,
    RateLimitConfig,
    SchedulerConfig,
    SlackConfig,
    StorageConfig,
    TelegramConfig,
    UserConfig,
)


def _make_config(
    *,
    telegram_enabled: bool = True,
    telegram_token: str = "t1",
    slack_enabled: bool = False,
    slack_bot_token: str = "",
    slack_app_token: str = "",
    pricing: dict[str, ModelPricingEntry] | None = None,
) -> AppConfig:
    return AppConfig(
        telegram=TelegramConfig(
            enabled=telegram_enabled,
            bot_token=SecretStr(telegram_token),
        ),
        slack=SlackConfig(
            enabled=slack_enabled,
            bot_token=SecretStr(slack_bot_token),
            app_token=SecretStr(slack_app_token),
        ),
        claude=ClaudeConfig(),
        storage=StorageConfig(),
        logging=LoggingConfig(),
        metrics=MetricsConfig(),
        scheduler=SchedulerConfig(),
        attachments=AttachmentsConfig(),
        users=[
            UserConfig(
                id="telegram:1",
                display_name="Me",
                allowed_tools=["Read"],
                rate_limit=RateLimitConfig(per_minute=20, per_day=1000),
            )
        ],
        cost=CostConfig(pricing=pricing or {}),
    )


class TestBuildUsers:
    def test_one_user(self) -> None:
        config = _make_config()
        users = main_module._build_users(config)
        assert len(users) == 1
        assert users[0].id == "telegram:1"
        assert users[0].display_name == "Me"
        assert users[0].allowed_tools == frozenset({"Read"})
        assert users[0].rate_limit_per_minute == 20
        assert users[0].rate_limit_per_day == 1000

    def test_multiple_users(self) -> None:
        config = _make_config()
        config = config.model_copy(
            update={
                "users": [
                    UserConfig(id="telegram:1", display_name="A"),
                    UserConfig(id="slack:U123", display_name="B"),
                    UserConfig(id="telegram:2", display_name="C"),
                ]
            }
        )
        users = main_module._build_users(config)
        ids = [u.id for u in users]
        assert ids == ["telegram:1", "slack:U123", "telegram:2"]


class TestBuildPricing:
    def test_empty_pricing(self) -> None:
        config = _make_config()
        assert main_module._build_pricing(config) == {}

    def test_multiple_models(self) -> None:
        pricing = {
            "claude-sonnet-4-6": ModelPricingEntry(
                input_usd_per_mtok=3.0, output_usd_per_mtok=15.0
            ),
            "claude-opus-4-6": ModelPricingEntry(input_usd_per_mtok=15.0, output_usd_per_mtok=75.0),
        }
        config = _make_config(pricing=pricing)
        built = main_module._build_pricing(config)
        assert set(built.keys()) == {"claude-sonnet-4-6", "claude-opus-4-6"}
        assert isinstance(built["claude-sonnet-4-6"], ModelPricing)
        assert built["claude-opus-4-6"].output_usd_per_mtok == 75.0


class _FakeAdapter:
    """Stands in for Telegram/Slack adapters during _build_adapters tests."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    async def run_forever(self) -> None:  # pragma: no cover - never called
        pass

    def build_reply_channel(self, channel_ref: str) -> ReplyChannel:  # pragma: no cover
        raise NotImplementedError


class _FakePipeline(MessagePipeline):
    def __init__(self) -> None:
        # Bypass the real __init__; we never call any pipeline method here.
        pass  # type: ignore[override]


class TestBuildAdapters:
    @pytest.fixture(autouse=True)
    def _patch_adapters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(main_module, "TelegramAdapter", _FakeAdapter)
        monkeypatch.setattr(main_module, "SlackAdapter", _FakeAdapter)

    def test_telegram_only(self) -> None:
        config = _make_config(telegram_enabled=True, telegram_token="t")
        adapters = main_module._build_adapters(config, _FakePipeline())
        assert list(adapters.keys()) == [Platform.TELEGRAM]

    def test_telegram_and_slack(self) -> None:
        config = _make_config(
            telegram_enabled=True,
            telegram_token="t",
            slack_enabled=True,
            slack_bot_token="xoxb-abc",
            slack_app_token="xapp-abc",
        )
        adapters = main_module._build_adapters(config, _FakePipeline())
        assert Platform.TELEGRAM in adapters
        assert Platform.SLACK in adapters

    def test_slack_enabled_but_missing_tokens_raises(self) -> None:
        config = _make_config(
            telegram_enabled=True,
            telegram_token="t",
            slack_enabled=True,
            slack_bot_token="",
            slack_app_token="",
        )
        with pytest.raises(ValueError, match=r"slack\.enabled=true"):
            main_module._build_adapters(config, _FakePipeline())

    def test_telegram_disabled_with_empty_token_excludes_it(self) -> None:
        config = _make_config(telegram_enabled=True, telegram_token="")
        # Empty token means effectively disabled — no adapter built.
        # But we need at least one adapter enabled or RuntimeError is raised.
        config_with_slack = config.model_copy(
            update={
                "slack": SlackConfig(
                    enabled=True,
                    bot_token=SecretStr("xoxb-abc"),
                    app_token=SecretStr("xapp-abc"),
                )
            }
        )
        adapters = main_module._build_adapters(config_with_slack, _FakePipeline())
        assert list(adapters.keys()) == [Platform.SLACK]

    def test_no_adapters_enabled_raises(self) -> None:
        config = _make_config(telegram_enabled=False)
        with pytest.raises(RuntimeError, match="No adapters are enabled"):
            main_module._build_adapters(config, _FakePipeline())


class TestRunUntilStopped:
    async def test_completes_when_all_runnables_return(self) -> None:
        class InstantRunnable:
            async def run_forever(self) -> None:
                return

        # Must not hang and must not raise.
        await main_module._run_until_stopped([InstantRunnable()])  # type: ignore[list-item]

    async def test_propagates_runnable_exception(self) -> None:
        class FailingRunnable:
            async def run_forever(self) -> None:
                raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await main_module._run_until_stopped([FailingRunnable()])  # type: ignore[list-item]

    async def test_cancellation_stops_the_runner(self) -> None:
        class SlowRunnable:
            async def run_forever(self) -> None:
                await asyncio.sleep(60)

        task = asyncio.create_task(
            main_module._run_until_stopped([SlowRunnable()])  # type: ignore[list-item]
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
