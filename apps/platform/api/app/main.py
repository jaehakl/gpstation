from initserver import server
from routers import web
from routers.app import v1 as app_v1


app = server()
app.include_router(web.router)
app.include_router(app_v1.router)
