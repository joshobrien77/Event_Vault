"""EventVault — FastAPI Application"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import auth, events, links, storage, uploads, guest, billing
from app.core.exceptions import AppError, app_error_handler, http_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.UPLOAD_TEMP_DIR).mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
    app.include_router(links.router, prefix="/api/v1/events", tags=["Event Links"])
    app.include_router(storage.router, prefix="/api/v1/events", tags=["Storage"])
    app.include_router(uploads.router, prefix="/api/v1/events", tags=["Uploads"])
    app.include_router(guest.router, prefix="/api/v1/e", tags=["Guest"])
    app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])

    @app.get("/api/v1/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "version": settings.APP_VERSION}

    return app


app = create_app()
