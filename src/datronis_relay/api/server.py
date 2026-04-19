"""aiohttp-based REST API server for the dashboard UI.

Satisfies the `_Runnable` protocol from `main.py` so it can be added
to the concurrent runnable list alongside adapters and the scheduler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from aiohttp import web

from datronis_relay.api.routes import build_routes

if TYPE_CHECKING:
    from datronis_relay.infrastructure.config import AppConfig
    from datronis_relay.infrastructure.sqlite_storage import SQLiteStorage

log = structlog.get_logger(__name__)

DEFAULT_API_PORT = 3100


class ApiServer:
    """HTTP API server that powers the dashboard UI."""

    def __init__(
        self,
        config: AppConfig,
        storage: SQLiteStorage,
        *,
        host: str = "0.0.0.0",
        port: int = DEFAULT_API_PORT,
    ) -> None:
        self._config = config
        self._storage = storage
        self._host = host
        self._port = port

    async def run_forever(self) -> None:
        app = web.Application(middlewares=[_cors_middleware])
        app["config"] = self._config
        app["storage"] = self._storage
        app["start_time"] = __import__("time").time()

        build_routes(app)

        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        log.info("api.server.start", host=self._host, port=self._port)

        # Block forever (until cancelled by the runner).
        try:
            while True:
                await __import__("asyncio").sleep(3600)
        finally:
            await runner.cleanup()


@web.middleware
async def _cors_middleware(
    request: web.Request,
    handler: web.RequestHandler,
) -> web.StreamResponse:
    """Allow cross-origin requests from the Next.js dev server."""
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response
