from initserver import server
from routers import users


app = server()
app.include_router(users.router)
