from fastapi import APIRouter
from app.api.routes import locations, analysis, team_properties

api_router = APIRouter()

api_router.include_router(locations.router)
api_router.include_router(analysis.router)
api_router.include_router(team_properties.router)
