from fastapi import APIRouter
from app.api.routes import (
    locations,
    analysis,
    properties,
    matrix,
    datasets,
    boundaries,
    team_properties,
    listings,
    opportunities,
    traffic,
    feedback,
    activity_nodes,
    scout,
    mission_control,
)

api_router = APIRouter()

api_router.include_router(locations.router)
api_router.include_router(analysis.router)
api_router.include_router(properties.router)
api_router.include_router(matrix.router)
api_router.include_router(datasets.router)
api_router.include_router(boundaries.router)
api_router.include_router(team_properties.router)
api_router.include_router(listings.router)
api_router.include_router(opportunities.router)
api_router.include_router(traffic.router, prefix="/traffic", tags=["traffic"])
api_router.include_router(feedback.router)
api_router.include_router(activity_nodes.router)
api_router.include_router(scout.router)
api_router.include_router(mission_control.router)
