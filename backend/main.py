from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from api.middleware import setup_middleware
from api.router import api_router
from core.config import settings
from core.logging import configure_logging
from services.mongo import mongo_service
from services.storage import storage_service


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info("OrthoAssist backend starting up...")
    logger.info("Environment: {} | Base URL: {} | Frontend: {}", settings.app_env, settings.resolved_server_base_url, settings.frontend_url)
    await storage_service.initialize()
    await mongo_service.initialize()
    logger.info("OrthoAssist startup complete. Storage and MongoDB ready.")
    yield
    await mongo_service.close()
    logger.info("OrthoAssist backend shut down.")


def create_app() -> FastAPI:
    configure_logging()  # set up loguru early so uvicorn logs are intercepted from the start
    app = FastAPI(
        title="OrthoAssist Backend",
        version="0.1.0",
        description="Agentic orthopedic backend with FastAPI, LangGraph, and MCP",
        lifespan=lifespan,
    )

    setup_middleware(app)
    app.include_router(api_router, prefix="/api")

    # Serve generated PDFs and uploaded images under /storage/*
    app.mount("/storage", StaticFiles(directory=str(settings.resolved_storage_path)), name="storage")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
