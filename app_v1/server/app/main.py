from app.initserver import server
from app.routers.v1 import routes as v1
from app.routers.web import routes as web


app = server()
app.include_router(web.router)
app.include_router(v1.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
