from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db import Base, SessionLocal, engine
from app.service.realtime_service import safe_close_client, stop_launcher_session
from app.service.session_service import SessionService
from app.service.launcher_service import LauncherService
from app.settings import settings, validate_runtime_settings
from app.state import runtime
from app.user_auth import db as user_auth_db

_ = user_auth_db

V1_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
    "Access-Control-Max-Age": "600",
}


class V1PublicCorsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not str(scope.get("path", "")).startswith("/v1/"):
            await self.app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        origin = request_headers.get("origin")
        if not origin:
            await self.app(scope, receive, send)
            return

        allow_headers = request_headers.get("access-control-request-headers") or "authorization, content-type"
        cors_headers = {
            **V1_CORS_HEADERS,
            "Access-Control-Allow-Headers": allow_headers,
        }

        if scope.get("method") == "OPTIONS" and request_headers.get("access-control-request-method"):
            await Response(status_code=200, headers=cors_headers)(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if "Access-Control-Allow-Credentials" in headers:
                    del headers["Access-Control-Allow-Credentials"]
                for name, value in cors_headers.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_cors)


def server() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await start()
        cleanup_task = asyncio.create_task(cleanup_expired_sessions())
        try:
            yield
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            print("service is stopped.")

    app = FastAPI(
        title="GP Station v1 Server",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(V1PublicCorsMiddleware)
    return app


async def start() -> None:
    validate_runtime_settings(settings)

    async with engine.begin() as conn:
        try:
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        await SessionService.mark_stale_sessions_error(db)
        await LauncherService.mark_stale_launchers_disconnected(db)

    print("service is started.")


async def cleanup_expired_sessions() -> None:
    while True:
        await asyncio.sleep(settings.cleanup_interval_seconds)
        async with SessionLocal() as db:
            expired_sessions = await SessionService.collect_expired_sessions(db)
        for db_session in expired_sessions:
            session = await runtime.close_session(str(db_session.id))
            launcher_id = session.launcher_id if session else str(db_session.launcher_id) if db_session.launcher_id else None
            if launcher_id is not None:
                await stop_launcher_session(launcher_id, str(db_session.id), "expired")
            if session is not None:
                await safe_close_client(session, "expired")
