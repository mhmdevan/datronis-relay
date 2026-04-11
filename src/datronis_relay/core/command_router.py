from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.interval_parser import format_interval, parse_interval
from datronis_relay.core.ports import (
    ClaudeClientProtocol,
    ScheduledTaskStoreProtocol,
)
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.messages import ClaudeRequest, PlatformMessage
from datronis_relay.domain.stream_events import CompletionEvent, StreamEvent, TextChunk
from datronis_relay.domain.user import User

HELP_TEXT = (
    "datronis-relay v0.4.0\n"
    "\n"
    "Commands:\n"
    "/start       — welcome + onboarding\n"
    "/help        — this message\n"
    "/ask         — send a prompt to Claude (default if you omit the command)\n"
    "/status      — show the current session id\n"
    "/stop        — reset the current session\n"
    "/cost        — your token usage and spend (today / 7d / 30d / total)\n"
    "/schedule    — /schedule <interval> <prompt>   e.g. /schedule 1h run tests\n"
    "/schedules   — list your scheduled tasks\n"
    "/unschedule  — /unschedule <task_id>\n"
    "\n"
    "Attachments: send a file or image to have Claude read it.\n"
)

WELCOME_TEXT = (
    "Hello — I'm datronis-relay.\n"
    "Send me any message and I'll ask Claude.\n"
    "Type /help for the full command list."
)


@dataclass(frozen=True, slots=True)
class StaticReply:
    """An immediate text reply that doesn't need streaming."""

    text: str


@dataclass(frozen=True, slots=True)
class StreamReply:
    """A streamed reply — the adapter consumes it with `async for`."""

    chunks: AsyncIterator[str]


Reply = StaticReply | StreamReply


class CommandRouter:
    """Routes inbound PlatformMessages to static or streamed replies.

    Dependencies are all injected ports. The router is platform-agnostic
    and knows nothing about Telegram, Slack, or the Claude SDK.

    `scheduled_store` is optional: when None, the `/schedule*` commands
    return a "scheduling is disabled" message instead of raising. This
    keeps the Phase 2/3 tests green without construction changes.
    """

    def __init__(
        self,
        claude: ClaudeClientProtocol,
        sessions: SessionManager,
        rate_limiter: RateLimiter,
        cost_tracker: CostTracker,
        scheduled_store: ScheduledTaskStoreProtocol | None = None,
        max_scheduled_tasks_per_user: int = 50,
    ) -> None:
        self._claude = claude
        self._sessions = sessions
        self._rate_limiter = rate_limiter
        self._cost_tracker = cost_tracker
        self._scheduled_store = scheduled_store
        self._max_scheduled_per_user = max_scheduled_tasks_per_user

    async def dispatch(self, message: PlatformMessage, user: User) -> Reply:
        command, argument = self._split_command(message.text)

        if command == "/start":
            return StaticReply(WELCOME_TEXT)
        if command == "/help":
            return StaticReply(HELP_TEXT)
        if command == "/status":
            session_id = await self._sessions.get_or_create(user.id)
            return StaticReply(f"session: {session_id}")
        if command == "/stop":
            await self._sessions.reset(user.id)
            return StaticReply("session reset.")
        if command == "/cost":
            return StaticReply(await self._format_cost(user))
        if command == "/schedule":
            return await self._handle_schedule(message, user, argument)
        if command == "/schedules":
            return await self._handle_list_schedules(user)
        if command == "/unschedule":
            return await self._handle_unschedule(user, argument)
        if command in ("/ask", None):
            return await self._handle_ask(message, user, command, argument)
        return StaticReply(f"unknown command: {command}")

    # ------------------------------------------------------------------ /ask

    async def _handle_ask(
        self,
        message: PlatformMessage,
        user: User,
        command: str | None,
        argument: str,
    ) -> Reply:
        prompt = argument if command == "/ask" else message.text
        has_attachments = len(message.attachments) > 0
        if not prompt.strip() and not has_attachments:
            return StaticReply("nothing to ask. send me a prompt.")

        await self._rate_limiter.check(
            user.id,
            per_minute=user.rate_limit_per_minute,
            per_day=user.rate_limit_per_day,
        )

        session_id = await self._sessions.get_or_create(user.id)
        request = ClaudeRequest(
            correlation_id=message.correlation_id,
            session_id=session_id,
            user_id=user.id,
            prompt=prompt if prompt.strip() else "Please look at the attached file(s).",
            allowed_tools=tuple(sorted(user.allowed_tools)),
            attachments=message.attachments,
        )
        return StreamReply(self._text_stream(self._claude.stream(request), user))

    async def _text_stream(
        self,
        events: AsyncIterator[StreamEvent],
        user: User,
    ) -> AsyncIterator[str]:
        async for event in events:
            if isinstance(event, TextChunk):
                if event.text:
                    yield event.text
            elif isinstance(event, CompletionEvent):
                await self._cost_tracker.record(
                    user_id=user.id,
                    tokens_in=event.usage.tokens_in,
                    tokens_out=event.usage.tokens_out,
                )

    # ----------------------------------------------------------------- /cost

    async def _format_cost(self, user: User) -> str:
        summary = await self._cost_tracker.summary(user.id)
        label = user.display_name or user.id
        return (
            f"cost summary for {label}:\n"
            f"today   : ${summary.today_cost_usd:.4f} "
            f"({summary.today_tokens_in} in / {summary.today_tokens_out} out)\n"
            f"7 days  : ${summary.week_cost_usd:.4f}\n"
            f"30 days : ${summary.month_cost_usd:.4f}\n"
            f"total   : ${summary.total_cost_usd:.4f}"
        )

    # -------------------------------------------------------------- /schedule

    async def _handle_schedule(
        self,
        message: PlatformMessage,
        user: User,
        argument: str,
    ) -> Reply:
        if self._scheduled_store is None:
            return StaticReply("scheduling is disabled on this server. ask the admin to enable it.")
        if not message.channel_ref:
            return StaticReply(
                "scheduling requires a chat channel — try this from a direct message."
            )

        parts = argument.strip().split(maxsplit=1)
        if len(parts) < 2:
            return StaticReply(
                "usage: /schedule <interval> <prompt>\n"
                "example: /schedule 1h check disk usage on prod-web-1"
            )
        interval_str, prompt = parts[0], parts[1].strip()
        if not prompt:
            return StaticReply("prompt cannot be empty.")

        try:
            interval_seconds = parse_interval(interval_str)
        except ValueError as exc:
            return StaticReply(f"invalid interval: {exc}")

        existing = await self._scheduled_store.count_scheduled_tasks(user.id)
        if existing >= self._max_scheduled_per_user:
            return StaticReply(
                f"you already have {existing} scheduled tasks "
                f"(max {self._max_scheduled_per_user}). "
                f"delete one with /unschedule <id> first."
            )

        task = await self._scheduled_store.create_scheduled_task(
            user_id=user.id,
            platform=message.platform,
            channel_ref=message.channel_ref,
            prompt=prompt,
            interval_seconds=interval_seconds,
        )
        return StaticReply(
            f"scheduled task #{task.id} every {format_interval(interval_seconds)}: "
            f"{_truncate(prompt, 80)}"
        )

    async def _handle_list_schedules(self, user: User) -> Reply:
        if self._scheduled_store is None:
            return StaticReply("scheduling is disabled on this server.")
        tasks = await self._scheduled_store.list_scheduled_tasks(user.id)
        if not tasks:
            return StaticReply("you have no scheduled tasks.")
        lines = ["your scheduled tasks:"]
        for t in tasks:
            lines.append(
                f"#{t.id}: every {format_interval(t.interval_seconds)} — {_truncate(t.prompt, 60)}"
            )
        return StaticReply("\n".join(lines))

    async def _handle_unschedule(self, user: User, argument: str) -> Reply:
        if self._scheduled_store is None:
            return StaticReply("scheduling is disabled on this server.")
        arg = argument.strip()
        if not arg:
            return StaticReply("usage: /unschedule <task_id>")
        try:
            task_id = int(arg)
        except ValueError:
            return StaticReply(f"invalid task id: {arg!r}")
        deleted = await self._scheduled_store.delete_scheduled_task(user.id, task_id)
        if deleted:
            return StaticReply(f"task #{task_id} deleted.")
        return StaticReply(f"no task #{task_id} found for you.")

    # ----------------------------------------------------------------- parsing

    @staticmethod
    def _split_command(text: str) -> tuple[str | None, str]:
        stripped = text.strip()
        if not stripped.startswith("/"):
            return None, stripped
        parts = stripped.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) == 2 else ""
        return cmd, arg


def _truncate(text: str, limit: int) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"
