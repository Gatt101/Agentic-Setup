from fastapi import FastAPI
from loguru import logger

from api.middleware import setup_middleware
from api.router import api_router
from core.config import settings
from core.logging import configure_logging
from services.mongo import mongo_service
from services.storage import storage_service


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="OrthoAssist Backend",
        version="0.1.0",
        description="Agentic orthopedic backend with FastAPI, LangGraph, and MCP",
    )

    setup_middleware(app)
    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    async def startup_event() -> None:
        logger.info("OrthoAssist backend starting up...")
        await storage_service.initialize()
        await mongo_service.initialize()
        logger.info("OrthoAssist startup complete. Storage and MongoDB ready.")

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        await mongo_service.close()

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
