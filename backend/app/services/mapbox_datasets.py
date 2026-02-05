"""
Mapbox Datasets API Service

Manages persistent GeoJSON datasets for saved analyses and custom layers.
Datasets can be exported to tilesets for efficient map rendering.

Key features:
- Create/update/delete datasets
- Add GeoJSON features to datasets
- Export datasets to tilesets
- Manage saved analyses

API Docs: https://docs.mapbox.com/api/maps/datasets/

Note: Requires access token with datasets:read, datasets:write, datasets:list scopes.
"""

import httpx
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from app.core.config import settings


class AnalysisType(str, Enum):
    """Types of saved analyses."""
    TRADE_AREA = "trade_area"
    MARKET_GAP = "market_gap"
    COVERAGE = "coverage"
    COMPETITOR = "competitor"
    DEMOGRAPHIC = "demographic"


class DatasetCreate(BaseModel):
    """Request model for creating a new dataset."""
    name: str = Field(..., max_length=64)
    description: str = Field(default="", max_length=500)


class DatasetInfo(BaseModel):
    """Information about a Mapbox dataset."""
    id: str
    owner: str
    name: str
    description: str
    created: datetime
    modified: datetime
    features: int = 0
    size: int = 0


class FeatureUpload(BaseModel):
    """A GeoJSON feature to upload to a dataset."""
    id: Optional[str] = None
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any] = Field(default_factory=dict)


class SavedAnalysisRequest(BaseModel):
    """Request to save an analysis as a dataset."""
    name: str
    analysis_type: AnalysisType
    center_latitude: float
    center_longitude: float
    geojson: Dict[str, Any]  # FeatureCollection
    config: Dict[str, Any] = Field(default_factory=dict)


class SavedAnalysisResponse(BaseModel):
    """Response after saving an analysis."""
    id: int  # Database ID
    dataset_id: str  # Mapbox dataset ID
    tileset_id: Optional[str] = None  # Mapbox tileset ID (if exported)
    name: str
    analysis_type: str
    center_latitude: float
    center_longitude: float
    created_at: datetime


# Base URL for Datasets API
DATASETS_API_BASE = "https://api.mapbox.com/datasets/v1"


def _get_username() -> str:
    """Get the Mapbox username from the access token."""
    # The username can be extracted from the token or configured separately
    # For simplicity, we'll use a configured value or default
    return getattr(settings, 'MAPBOX_USERNAME', 'msrodtn')


async def create_dataset(name: str, description: str = "") -> DatasetInfo:
    """
    Create a new Mapbox dataset.

    Args:
        name: Dataset name (max 64 characters)
        description: Optional description (max 500 characters)

    Returns:
        DatasetInfo with the created dataset details
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    username = _get_username()
    url = f"{DATASETS_API_BASE}/{username}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            params={"access_token": settings.MAPBOX_ACCESS_TOKEN},
            json={"name": name, "description": description},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return DatasetInfo(
        id=data["id"],
        owner=data["owner"],
        name=data.get("name", ""),
        description=data.get("description", ""),
        created=datetime.fromisoformat(data["created"].replace("Z", "+00:00")),
        modified=datetime.fromisoformat(data["modified"].replace("Z", "+00:00")),
        features=data.get("features", 0),
        size=data.get("size", 0),
    )


async def list_datasets() -> List[DatasetInfo]:
    """
    List all datasets for the authenticated user.

    Returns:
        List of DatasetInfo objects
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    username = _get_username()
    url = f"{DATASETS_API_BASE}/{username}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={"access_token": settings.MAPBOX_ACCESS_TOKEN},
            timeout=30.0,
        )
        response.raise_for_status()
        datasets = response.json()

    return [
        DatasetInfo(
            id=d["id"],
            owner=d["owner"],
            name=d.get("name", ""),
            description=d.get("description", ""),
            created=datetime.fromisoformat(d["created"].replace("Z", "+00:00")),
            modified=datetime.fromisoformat(d["modified"].replace("Z", "+00:00")),
            features=d.get("features", 0),
            size=d.get("size", 0),
        )
        for d in datasets
    ]


async def get_dataset(dataset_id: str) -> DatasetInfo:
    """
    Get information about a specific dataset.

    Args:
        dataset_id: The dataset ID

    Returns:
        DatasetInfo with dataset details
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    username = _get_username()
    url = f"{DATASETS_API_BASE}/{username}/{dataset_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={"access_token": settings.MAPBOX_ACCESS_TOKEN},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return DatasetInfo(
        id=data["id"],
        owner=data["owner"],
        name=data.get("name", ""),
        description=data.get("description", ""),
        created=datetime.fromisoformat(data["created"].replace("Z", "+00:00")),
        modified=datetime.fromisoformat(data["modified"].replace("Z", "+00:00")),
        features=data.get("features", 0),
        size=data.get("size", 0),
    )


async def delete_dataset(dataset_id: str) -> bool:
    """
    Delete a dataset.

    Args:
        dataset_id: The dataset ID to delete

    Returns:
        True if successful
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    username = _get_username()
    url = f"{DATASETS_API_BASE}/{username}/{dataset_id}"

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            url,
            params={"access_token": settings.MAPBOX_ACCESS_TOKEN},
            timeout=30.0,
        )
        response.raise_for_status()

    return True


async def upload_features(
    dataset_id: str,
    features: List[FeatureUpload],
) -> int:
    """
    Upload GeoJSON features to a dataset.

    Args:
        dataset_id: The target dataset ID
        features: List of GeoJSON features to upload

    Returns:
        Number of features uploaded
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    username = _get_username()
    uploaded_count = 0

    async with httpx.AsyncClient() as client:
        for i, feature in enumerate(features):
            # Generate feature ID if not provided
            feature_id = feature.id or f"feature-{i}-{datetime.utcnow().timestamp()}"

            url = f"{DATASETS_API_BASE}/{username}/{dataset_id}/features/{feature_id}"

            feature_data = {
                "id": feature_id,
                "type": feature.type,
                "geometry": feature.geometry,
                "properties": feature.properties,
            }

            response = await client.put(
                url,
                params={"access_token": settings.MAPBOX_ACCESS_TOKEN},
                json=feature_data,
                timeout=30.0,
            )
            response.raise_for_status()
            uploaded_count += 1

    return uploaded_count


async def upload_feature_collection(
    dataset_id: str,
    feature_collection: Dict[str, Any],
) -> int:
    """
    Upload a GeoJSON FeatureCollection to a dataset.

    Args:
        dataset_id: The target dataset ID
        feature_collection: GeoJSON FeatureCollection

    Returns:
        Number of features uploaded
    """
    features = [
        FeatureUpload(
            id=f.get("id"),
            type=f.get("type", "Feature"),
            geometry=f["geometry"],
            properties=f.get("properties", {}),
        )
        for f in feature_collection.get("features", [])
    ]

    return await upload_features(dataset_id, features)


async def get_features(
    dataset_id: str,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Get features from a dataset as a GeoJSON FeatureCollection.

    Args:
        dataset_id: The dataset ID
        limit: Maximum features to return

    Returns:
        GeoJSON FeatureCollection
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    username = _get_username()
    url = f"{DATASETS_API_BASE}/{username}/{dataset_id}/features"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={
                "access_token": settings.MAPBOX_ACCESS_TOKEN,
                "limit": limit,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return data


async def export_to_tileset(
    dataset_id: str,
    tileset_id: str,
    tileset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export a dataset to a tileset for efficient map rendering.

    Note: This uses the Uploads API which requires additional configuration.
    The tileset will be available at mapbox://username.tileset_id

    Args:
        dataset_id: Source dataset ID
        tileset_id: Target tileset ID (will be prefixed with username)
        tileset_name: Optional tileset name

    Returns:
        Upload status information
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    username = _get_username()

    # First, get the dataset as GeoJSON
    features = await get_features(dataset_id, limit=10000)

    # Use Uploads API to create tileset
    # Note: This is a simplified implementation
    # Full implementation would use S3 staging for large datasets
    uploads_url = f"https://api.mapbox.com/uploads/v1/{username}"

    async with httpx.AsyncClient() as client:
        # Create upload from GeoJSON
        response = await client.post(
            uploads_url,
            params={"access_token": settings.MAPBOX_ACCESS_TOKEN},
            json={
                "tileset": f"{username}.{tileset_id}",
                "name": tileset_name or tileset_id,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# Saved Analyses Management (Database-backed)
# ============================================================================

# In-memory storage for development (replace with database in production)
_saved_analyses: Dict[int, Dict[str, Any]] = {}
_next_analysis_id = 1


async def save_analysis(request: SavedAnalysisRequest) -> SavedAnalysisResponse:
    """
    Save an analysis to Mapbox Datasets and local database.

    Args:
        request: SavedAnalysisRequest with analysis details

    Returns:
        SavedAnalysisResponse with dataset information
    """
    global _next_analysis_id

    # Create dataset in Mapbox
    dataset = await create_dataset(
        name=request.name[:64],
        description=f"{request.analysis_type.value} analysis at ({request.center_latitude:.4f}, {request.center_longitude:.4f})",
    )

    # Upload features to dataset
    if "features" in request.geojson:
        await upload_feature_collection(dataset.id, request.geojson)

    # Save to local storage (database in production)
    analysis_id = _next_analysis_id
    _next_analysis_id += 1

    saved_analysis = {
        "id": analysis_id,
        "dataset_id": dataset.id,
        "tileset_id": None,
        "name": request.name,
        "analysis_type": request.analysis_type.value,
        "center_latitude": request.center_latitude,
        "center_longitude": request.center_longitude,
        "config": request.config,
        "created_at": datetime.utcnow(),
    }
    _saved_analyses[analysis_id] = saved_analysis

    return SavedAnalysisResponse(
        id=analysis_id,
        dataset_id=dataset.id,
        tileset_id=None,
        name=request.name,
        analysis_type=request.analysis_type.value,
        center_latitude=request.center_latitude,
        center_longitude=request.center_longitude,
        created_at=saved_analysis["created_at"],
    )


async def list_saved_analyses() -> List[SavedAnalysisResponse]:
    """
    List all saved analyses.

    Returns:
        List of SavedAnalysisResponse objects
    """
    return [
        SavedAnalysisResponse(
            id=a["id"],
            dataset_id=a["dataset_id"],
            tileset_id=a.get("tileset_id"),
            name=a["name"],
            analysis_type=a["analysis_type"],
            center_latitude=a["center_latitude"],
            center_longitude=a["center_longitude"],
            created_at=a["created_at"],
        )
        for a in _saved_analyses.values()
    ]


async def get_saved_analysis(analysis_id: int) -> Optional[SavedAnalysisResponse]:
    """
    Get a specific saved analysis.

    Args:
        analysis_id: The analysis ID

    Returns:
        SavedAnalysisResponse or None if not found
    """
    if analysis_id not in _saved_analyses:
        return None

    a = _saved_analyses[analysis_id]
    return SavedAnalysisResponse(
        id=a["id"],
        dataset_id=a["dataset_id"],
        tileset_id=a.get("tileset_id"),
        name=a["name"],
        analysis_type=a["analysis_type"],
        center_latitude=a["center_latitude"],
        center_longitude=a["center_longitude"],
        created_at=a["created_at"],
    )


async def delete_saved_analysis(analysis_id: int) -> bool:
    """
    Delete a saved analysis and its associated dataset.

    Args:
        analysis_id: The analysis ID to delete

    Returns:
        True if successful
    """
    if analysis_id not in _saved_analyses:
        return False

    analysis = _saved_analyses[analysis_id]

    # Delete dataset from Mapbox
    try:
        await delete_dataset(analysis["dataset_id"])
    except Exception:
        pass  # Dataset may already be deleted

    # Remove from local storage
    del _saved_analyses[analysis_id]

    return True
