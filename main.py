from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.auth import router as authrouter
from routers.profile import router as profilerouter
from routers.projects import router as projectrouter
from routers.search import router as searchrouter
from routers.application import router as applicationrouter
from routers.management import router as managementrouter
from routers.chat import router as chatrouter
from routers.skills import router as skillrouter
from routers.upload import router as uploadrouter
from config import FRONTEND_LINK
app = FastAPI(title="Filmo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_LINK],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(authrouter)
app.include_router(profilerouter)
app.include_router(projectrouter)
app.include_router(searchrouter)
app.include_router(applicationrouter)
app.include_router(managementrouter)
app.include_router(chatrouter)
app.include_router(skillrouter)
app.include_router(uploadrouter)

@app.get("/")
def root():
    return {"message": "Filmo API"}