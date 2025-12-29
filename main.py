from fastapi import FastAPI
from routers.auth import router as authrouter

app = FastAPI()

app.include_router(authrouter)
