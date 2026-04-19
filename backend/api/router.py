from fastapi import APIRouter

from api.endpoints.analyze import router as analyze_router
from api.endpoints.chat import router as chat_router
from api.endpoints.dashboard import router as dashboard_router
from api.endpoints.feedback import router as feedback_router
from api.endpoints.health import router as health_router
from api.endpoints.knowledge import router as knowledge_router
from api.endpoints.metrics import router as metrics_router
from api.endpoints.multi_agent import router as multi_agent_router
from api.endpoints.nearby import router as nearby_router
from api.endpoints.patients import router as patients_router
from api.endpoints.reports import router as reports_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(metrics_router)
api_router.include_router(dashboard_router)
api_router.include_router(analyze_router)
api_router.include_router(patients_router)
api_router.include_router(chat_router)
api_router.include_router(reports_router)
api_router.include_router(knowledge_router)
api_router.include_router(nearby_router)
api_router.include_router(feedback_router)
api_router.include_router(multi_agent_router)
