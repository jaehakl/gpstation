from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import Base, engine
from settings import settings


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
        allow_methods=["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    async def start():
        app.state.progress = 0
        async with engine.begin() as conn:
            try:
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            except Exception:
                pass
            await conn.run_sync(Base.metadata.create_all)
            await conn.exec_driver_sql("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'unauthorized';")
            await conn.exec_driver_sql(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'ck_users_role'
                    ) THEN
                        ALTER TABLE users
                        ADD CONSTRAINT ck_users_role
                        CHECK (role IN ('admin','user','unauthorized')) NOT VALID;
                    END IF;
                END $$;
                """
            )

        print("service is started.")

    def shutdown():
        print("service is stopped.")

    return app
