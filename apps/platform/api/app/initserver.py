from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import Base, engine
from settings import settings
from user_auth.routes import router as auth_router


def server():
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await start()
        yield
        shutdown()

    app = FastAPI(lifespan=lifespan)

    origins = [
        "http://localhost",
        "http://localhost:3000",
        settings.app_base_url,
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)

    async def start():
        app.state.progress = 0
        async with engine.begin() as conn:
            try:
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            except Exception:
                pass
            await conn.run_sync(Base.metadata.create_all)

        print("service is started.")

    def shutdown():
        print("service is stopped.")

    return app
