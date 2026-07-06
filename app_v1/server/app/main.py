from app.initserver import server
from app.routers import v1


app = server()
app.include_router(v1.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
