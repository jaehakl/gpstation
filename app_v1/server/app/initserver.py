from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db import Base, SessionLocal, engine
from app.service.launcher_service import LauncherService
from app.settings import settings, validate_runtime_settings
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
        try:
            yield
        finally:
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
        await conn.exec_driver_sql("DROP TABLE IF EXISTS slave_sessions CASCADE;")
        await conn.exec_driver_sql("ALTER TABLE launchers DROP COLUMN IF EXISTS active_session_ids;")
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        await LauncherService.mark_stale_launchers_disconnected(db)

    print("service is started.")
