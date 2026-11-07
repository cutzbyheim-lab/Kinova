from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import brands, jobs, media, projects, system
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()
settings = get_settings()

app = FastAPI(
    title="KINOVA API",
    version="0.1.0",
    description="AI content production & marketing automation platform.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (system.router, brands.router, projects.router, media.router, jobs.router):
    app.include_router(r)
