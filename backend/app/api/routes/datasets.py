"""
Datasets API endpoints (Saved Analyses via Mapbox Datasets).

Includes:
- Save analysis to Mapbox Dataset
- List/get/delete saved analyses
- List raw Mapbox datasets
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.mapbox_datasets import (
    SavedAnalysisRequest,
    SavedAnalysisResponse,
    DatasetInfo,
    AnalysisType,
    save_analysis,
    list_saved_analyses,
    get_saved_analysis,
    delete_saved_analysis,
    list_datasets,
    get_dataset,
    get_features,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


class SaveAnalysisRequestBody(BaseModel):
    """Request body for saving an analysis."""
    name: str
    analysis_type: str  # trade_area, market_gap, coverage, competitor, demographic
    center_latitude: float
    center_longitude: float
    geojson: dict  # GeoJSON FeatureCollection
    config: Optional[dict] = None


@router.post("/datasets/save/", response_model=SavedAnalysisResponse)
async def save_analysis_endpoint(request: SaveAnalysisRequestBody):
    """
    Save an analysis as a Mapbox dataset.

    **Analysis Types:** trade_area, market_gap, coverage, competitor, demographic
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    try:
        analysis_type = AnalysisType(request.analysis_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid analysis type: {request.analysis_type}. Valid types: {[t.value for t in AnalysisType]}"
        )

    try:
        result = await save_analysis(
            SavedAnalysisRequest(
                name=request.name,
                analysis_type=analysis_type,
                center_latitude=request.center_latitude,
                center_longitude=request.center_longitude,
                geojson=request.geojson,
                config=request.config or {},
            )
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving analysis: {str(e)}")


@router.get("/datasets/", response_model=list[SavedAnalysisResponse])
async def list_saved_analyses_endpoint():
    """List all saved analyses."""
    try:
        return await list_saved_analyses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing analyses: {str(e)}")


@router.get("/datasets/{analysis_id}/", response_model=SavedAnalysisResponse)
async def get_saved_analysis_endpoint(analysis_id: int):
    """Get a specific saved analysis."""
    result = await get_saved_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return result


@router.get("/datasets/{analysis_id}/features/")
async def get_analysis_features_endpoint(analysis_id: int, limit: int = 100):
    """Get the GeoJSON features from a saved analysis."""
    analysis = await get_saved_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    try:
        features = await get_features(analysis.dataset_id, limit=limit)
        return features
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching features: {str(e)}")


@router.delete("/datasets/{analysis_id}/")
async def delete_saved_analysis_endpoint(analysis_id: int):
    """Delete a saved analysis (local DB record + Mapbox dataset)."""
    success = await delete_saved_analysis(analysis_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return {"status": "success", "message": f"Analysis {analysis_id} deleted"}


@router.get("/datasets/mapbox/")
async def list_mapbox_datasets_endpoint():
    """List all Mapbox datasets for the authenticated user."""
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    try:
        datasets = await list_datasets()
        return [d.model_dump() for d in datasets]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing Mapbox datasets: {str(e)}")
