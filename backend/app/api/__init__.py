from fastapi import APIRouter
from app.api.routes import locations

api_router = APIRouter()

api_router.include_router(locations.router)
