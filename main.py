from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
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
from utils.scheduler import start_scheduler, stop_scheduler
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    logger.info("Application started")
    yield
    # Shutdown
    stop_scheduler()
    logger.info("Application shutdown")

app = FastAPI(
    title="Filmo API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - Combined into one middleware with multiple origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_LINK,
        "http://localhost:5173",
        "http://localhost:3000"  # Add any other dev URLs
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Filmo API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include routers
app.include_router(authrouter)
app.include_router(profilerouter)
app.include_router(projectrouter)
app.include_router(searchrouter)
app.include_router(applicationrouter)
app.include_router(managementrouter)
app.include_router(chatrouter)
app.include_router(skillrouter)
app.include_router(uploadrouter)