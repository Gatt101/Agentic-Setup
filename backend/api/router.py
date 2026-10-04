from fastapi import APIRouter, Depends

from api.endpoints.chat import router as chat_router
from api.endpoints.dashboard import router as dashboard_router
from api.endpoints.health import router as health_router
from api.endpoints.patients import router as patients_router
from api.endpoints.reports import router as reports_router
from core.auth import require_doctor


api_router = APIRouter()
api_router.include_router(health_router)

doctor_router = APIRouter(dependencies=[Depends(require_doctor)])
doctor_router.include_router(dashboard_router)
doctor_router.include_router(patients_router)
doctor_router.include_router(chat_router)
doctor_router.include_router(reports_router)
api_router.include_router(doctor_router)
