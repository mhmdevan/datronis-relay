from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
import sys
from pathlib import Path
from typing import Protocol

import structlog

from datronis_relay import __version__
from datronis_relay.adapters.slack.bot import SlackAdapter
from datronis_relay.adapters.telegram.bot import TelegramAdapter
from datronis_relay.cli.doctor import DoctorOptions, run_doctor
from datronis_relay.cli.setup import DEFAULT_CONFIG_PATH, DEFAULT_ENV_PATH, SetupOptions, run_setup
from datronis_relay.core.auth import AuthGuard
from datronis_relay.core.command_router import CommandRouter
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.core.scheduler import AdapterRegistry, Scheduler
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.ids import UserId
from datronis_relay.domain.messages import Platform
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.domain.user import User
from datronis_relay.infrastructure.claude_client import ClaudeAgentClient
from datronis_relay.infrastructure.config import AppConfig
from datronis_relay.infrastructure.formatting import (
    PassthroughFormatter,
    SlackMrkdwnFormatter,
    TelegramHtmlFormatter,
)
from datronis_relay.infrastructure.logging import configure_logging
from datronis_relay.api import ApiServer
from datronis_relay.cli.banner import print_banner
from datronis_relay.infrastructure.metrics import start_metrics_server
from datronis_relay.infrastructure.sqlite_storage import SQLiteStorage

log = structlog.get_logger(__name__)


class _ChatAdapter(Protocol):
    """Structural type every adapter must satisfy for the runner."""

    async def run_forever(self) -> None: ...

    def build_reply_channel(self, channel_ref: str) -> ReplyChannel: ...


class _Runnable(Protocol):
    """Structural type for everything the runner awaits concurrently —
    adapters and the scheduler both satisfy this."""

    async def run_forever(self) -> None: ...


def _build_users(config: AppConfig) -> list[User]:
    return [
        User(
            id=UserId(u.id),
            display_name=u.display_name,
            allowed_tools=frozenset(u.allowed_tools),
            rate_limit_per_minute=u.rate_limit.per_minute,
            rate_limit_per_day=u.rate_limit.per_day,
        )
        for u in config.users
    ]


def _build_pricing(config: AppConfig) -> dict[str, ModelPricing]:
    return {
        model_name: ModelPricing(
            input_usd_per_mtok=entry.input_usd_per_mtok,
            output_usd_per_mtok=entry.output_usd_per_mtok,
        )
        for model_name, entry in config.cost.pricing.items()
    }


def _build_adapters(config: AppConfig, pipeline: MessagePipeline) -> dict[Platform, _ChatAdapter]:
    adapters: dict[Platform, _ChatAdapter] = {}

    if config.telegram.enabled and config.telegram.bot_token.get_secret_value():
        adapters[Platform.TELEGRAM] = TelegramAdapter(
            token=config.telegram.bot_token.get_secret_value(),
            pipeline=pipeline,
            attachments_temp_dir=config.attachments.temp_dir,
            max_attachment_bytes=config.attachments.max_bytes_per_file,
        )
        log.info("adapter.enabled", adapter="telegram")

    if config.slack.enabled:
        bot = config.slack.bot_token.get_secret_value()
        app = config.slack.app_token.get_secret_value()
        if not bot or not app:
            raise ValueError(
                "slack.enabled=true but slack.bot_token and/or slack.app_token "
                "are missing. Set them in config.yaml, or via "
                "DATRONIS_SLACK_BOT_TOKEN and DATRONIS_SLACK_APP_TOKEN."
            )
        adapters[Platform.SLACK] = SlackAdapter(
            bot_token=bot,
            app_token=app,
            pipeline=pipeline,
            attachments_temp_dir=config.attachments.temp_dir,
            max_attachment_bytes=config.attachments.max_bytes_per_file,
        )
        log.info("adapter.enabled", adapter="slack")

    if not adapters:
        raise RuntimeError(
            "No adapters are enabled. Enable at least one of telegram/slack in config.yaml."
        )
    return adapters


async def _run() -> None:
    config = AppConfig.load()
    configure_logging(level=config.logging.level, json_output=config.logging.json_output)
    if sys.stdin.isatty():
        print_banner()
    log.info("datronis.relay.start", version=__version__)

    storage = SQLiteStorage(config.storage.sqlite_path)
    await storage.open()

    try:
        sessions = SessionManager(storage)
        rate_limiter = RateLimiter()
        cost_tracker = CostTracker(
            store=storage,
            pricing=_build_pricing(config),
            default_model=config.claude.model,
        )
        claude = ClaudeAgentClient(
            model=config.claude.model,
            max_turns=config.claude.max_turns,
        )
        router = CommandRouter(
            claude=claude,
            sessions=sessions,
            rate_limiter=rate_limiter,
            cost_tracker=cost_tracker,
            scheduled_store=storage,
            max_scheduled_tasks_per_user=config.scheduler.max_tasks_per_user,
        )
        auth = AuthGuard(users=_build_users(config))
        # Per-platform formatters:
        #   Phase M-1: Telegram gets TelegramHtmlFormatter (real Telegram
        #     HTML rendering — headings, lists, code, tables, etc.).
        #   Phase M-2 (next): Slack gets SlackMrkdwnFormatter — today
        #     it still uses PassthroughFormatter so Slack messages look
        #     the same as before M-1.
        pipeline = MessagePipeline(
            auth=auth,
            router=router,
            formatter=PassthroughFormatter(),  # fallback
            formatters={
                Platform.TELEGRAM: TelegramHtmlFormatter(),
                Platform.SLACK: SlackMrkdwnFormatter(),
            },
        )

        adapters = _build_adapters(config, pipeline)
        registry = AdapterRegistry(adapters=dict(adapters))

        runnables: list[_Runnable] = list(adapters.values())
        if config.scheduler.enabled:
            scheduler = Scheduler(
                store=storage,
                pipeline=pipeline,
                registry=registry,
                poll_interval_seconds=config.scheduler.poll_interval_seconds,
                batch_limit=config.scheduler.batch_limit,
            )
            runnables.append(scheduler)
            log.info("scheduler.enabled")

        if config.metrics.enabled:
            start_metrics_server(host=config.metrics.host, port=config.metrics.port)

        # Dashboard API server — always enabled so the UI works out of the box.
        api_server = ApiServer(config=config, storage=storage)
        runnables.append(api_server)
        log.info("api.server.enabled", port=3100)

        await _run_until_stopped(runnables)
    finally:
        await storage.close()
    log.info("datronis.relay.stop")


async def _run_until_stopped(runnables: list[_Runnable]) -> None:
    """Run every adapter + the scheduler concurrently until a stop signal
    or the first failure. Fail-loud: if any component raises, all others
    are cancelled and the process exits for the supervisor to restart."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle_stop() -> None:
        log.info("datronis.relay.signal_received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # pragma: no cover — Windows
            loop.add_signal_handler(sig, _handle_stop)

    runnable_tasks = [
        asyncio.create_task(r.run_forever(), name=f"runnable-{type(r).__name__}") for r in runnables
    ]
    stop_task = asyncio.create_task(stop_event.wait(), name="stop-signal")

    done, pending = await asyncio.wait(
        [*runnable_tasks, stop_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    for task in done:
        if task is stop_task:
            continue
        exc = task.exception()
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            log.error("datronis.relay.component_failed", error=str(exc))
            raise exc


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datronis-relay",
        description=(
            "Chat bridge for the Claude Agent SDK. Run with no arguments to "
            "start the bot; use a subcommand to set up or validate your config."
        ),
    )
    parser.add_argument("--version", action="version", version=f"datronis-relay {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    setup_parser = subparsers.add_parser(
        "setup",
        help="Interactive setup wizard — creates config.yaml and .env",
    )
    setup_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the config file to write (default: ./config.yaml)",
    )
    setup_parser.add_argument(
        "--env",
        default=str(DEFAULT_ENV_PATH),
        help="Path to the .env file to write (default: ./.env)",
    )
    setup_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config without prompting",
    )
    setup_parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip the api.telegram.org/getMe network check",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Validate an existing config and report problems",
    )
    doctor_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the config file to check (default: ./config.yaml)",
    )

    return parser


def _dispatch_subcommand(args: argparse.Namespace) -> int:
    """Route a parsed argparse namespace to the right CLI handler."""
    if args.command == "setup":
        return run_setup(
            SetupOptions(
                config_path=Path(args.config),
                env_path=Path(args.env),
                force=args.force,
                skip_validation=args.skip_validation,
            )
        )
    if args.command == "doctor":
        return run_doctor(DoctorOptions(config_path=Path(args.config)))
    raise AssertionError(f"unknown subcommand: {args.command}")  # pragma: no cover


def _maybe_offer_first_run_setup() -> bool:
    """If no config exists and stdin is a TTY, offer to run the wizard.

    Returns True if setup was run successfully (caller should continue to
    the bot), False if setup was declined or failed (caller should error
    out with the original "config missing" message).
    """
    config_path = Path(os.getenv("DATRONIS_CONFIG_PATH") or DEFAULT_CONFIG_PATH)
    if config_path.exists():
        return False  # not a first run, nothing to offer
    if not sys.stdin.isatty():
        return False  # headless (Docker, systemd) — fail loudly via _run()

    print_banner()
    print()
    print(f"No config file found at {config_path}.")
    print()
    response = input("Run the setup wizard now? [Y/n]: ").strip().lower()
    if response not in ("", "y", "yes"):
        print("Aborted. Run `datronis-relay setup` when you're ready.")
        sys.exit(1)

    result = run_setup(SetupOptions(config_path=config_path))
    if result != 0:
        sys.exit(result)
    return True


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.command is not None:
        sys.exit(_dispatch_subcommand(args))

    # No subcommand — start the bot. If config is missing and we're on a
    # TTY, offer to run the wizard first.
    _maybe_offer_first_run_setup()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
