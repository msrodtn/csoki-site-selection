"""
Mission Control Integration API endpoints.

Provides job management, market intelligence, and site recommendations
for Mission Control agents.
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel, Field
from sqlalchemy import text, func, and_, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.analysis_job import AnalysisJob, JobStatus, JobPriority

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mc", tags=["mission-control"])

# =============================================================================
# Authentication
# =============================================================================

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify Mission Control API key."""
    # TODO: In production, use a proper API key system
    # For now, we'll check against an environment variable
    expected_key = settings.MISSION_CONTROL_API_KEY if hasattr(settings, 'MISSION_CONTROL_API_KEY') else None
    
    # If no key is configured, allow access (for development)
    if expected_key is None:
        logger.warning("Mission Control API key not configured - allowing unauthenticated access")
        return True
    
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateJobRequest(BaseModel):
    """Request to create a new analysis job."""
    market: str = Field(..., description="Target market (Iowa, Nebraska, Nevada, Idaho)")
    criteria: List[str] = Field(..., description="Analysis criteria (demographics, competitors, traffic)")
    priority: JobPriority = Field(JobPriority.MEDIUM, description="Job priority")
    requested_by: str = Field(..., description="Mission Control agent ID")
    callback_url: Optional[str] = Field(None, description="Webhook URL for completion notification")


class JobResponse(BaseModel):
    """Analysis job response."""
    job_id: str
    market: str
    criteria: List[str]
    priority: str
    requested_by: str
    callback_url: Optional[str]
    status: str
    progress: float
    status_message: Optional[str]
    results: Optional[dict]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_completion: Optional[datetime]
    execution_time_seconds: Optional[float]

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """List of analysis jobs with pagination."""
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


class MarketSummary(BaseModel):
    """Summary statistics for a market."""
    market: str
    total_stores: int
    stores_by_brand: dict
    saturation_score: Optional[float] = Field(None, description="0-100 score indicating market saturation")
    growth_opportunities: Optional[str] = Field(None, description="Brief assessment of growth potential")
    recent_changes: Optional[str] = Field(None, description="Recent market changes if any")


# =============================================================================
# Job Management Endpoints
# =============================================================================

@router.post("/jobs/", response_model=JobResponse, dependencies=[Depends(verify_api_key)])
async def create_analysis_job(request: CreateJobRequest, db: Session = Depends(get_db)):
    """
    Create a new site analysis job.
    
    This endpoint queues a new analysis job that will be processed asynchronously.
    The job status can be polled via GET /mc/jobs/{job_id}.
    """
    # Validate market
    valid_markets = ["Iowa", "Nebraska", "Nevada", "Idaho"]
    if request.market not in valid_markets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid market. Must be one of: {', '.join(valid_markets)}"
        )
    
    # Validate criteria
    valid_criteria = ["demographics", "competitors", "traffic"]
    invalid_criteria = [c for c in request.criteria if c not in valid_criteria]
    if invalid_criteria:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid criteria: {', '.join(invalid_criteria)}. Must be one of: {', '.join(valid_criteria)}"
        )
    
    # Generate job ID
    job_id = f"csoki-job-{uuid.uuid4().hex[:12]}"
    
    # Estimate completion time (rough estimate based on criteria count)
    minutes_per_criterion = 2
    estimated_minutes = len(request.criteria) * minutes_per_criterion
    estimated_completion = datetime.utcnow() + timedelta(minutes=estimated_minutes)
    
    # Create job record
    job = AnalysisJob(
        id=job_id,
        market=request.market,
        criteria=request.criteria,
        priority=request.priority,
        requested_by=request.requested_by,
        callback_url=request.callback_url,
        status=JobStatus.PENDING,
        progress=0.0,
        status_message="Job created, waiting to start",
        estimated_completion=estimated_completion
    )
    
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
        
        logger.info(f"Created analysis job {job_id} for market {request.market} by {request.requested_by}")
        
        # TODO: Trigger actual analysis processing (background task, worker queue, etc.)
        # For now, jobs will remain in PENDING status until we implement the worker
        
        return JobResponse(
            job_id=job.id,
            market=job.market,
            criteria=job.criteria,
            priority=job.priority.value,
            requested_by=job.requested_by,
            callback_url=job.callback_url,
            status=job.status.value,
            progress=job.progress,
            status_message=job.status_message,
            results=job.results,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            estimated_completion=job.estimated_completion,
            execution_time_seconds=job.execution_time_seconds
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating analysis job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating job: {str(e)}")


@router.get("/jobs/{job_id}", response_model=JobResponse, dependencies=[Depends(verify_api_key)])
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Get the status of an analysis job.
    
    Returns job details including current status, progress, and results if completed.
    """
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobResponse(
        job_id=job.id,
        market=job.market,
        criteria=job.criteria,
        priority=job.priority.value,
        requested_by=job.requested_by,
        callback_url=job.callback_url,
        status=job.status.value,
        progress=job.progress,
        status_message=job.status_message,
        results=job.results,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        estimated_completion=job.estimated_completion,
        execution_time_seconds=job.execution_time_seconds
    )


@router.get("/jobs/", response_model=JobListResponse, dependencies=[Depends(verify_api_key)])
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    market: Optional[str] = Query(None, description="Filter by market"),
    requested_by: Optional[str] = Query(None, description="Filter by requester agent ID"),
    limit: int = Query(20, ge=1, le=100, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    db: Session = Depends(get_db)
):
    """
    List analysis jobs with optional filtering.
    
    Supports filtering by status, market, and requester. Results are paginated.
    """
    # Build query with filters
    query = db.query(AnalysisJob)
    
    if status:
        query = query.filter(AnalysisJob.status == status)
    
    if market:
        query = query.filter(AnalysisJob.market == market)
    
    if requested_by:
        query = query.filter(AnalysisJob.requested_by == requested_by)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering (newest first)
    jobs = query.order_by(AnalysisJob.created_at.desc()).offset(offset).limit(limit).all()
    
    job_responses = [
        JobResponse(
            job_id=job.id,
            market=job.market,
            criteria=job.criteria,
            priority=job.priority.value,
            requested_by=job.requested_by,
            callback_url=job.callback_url,
            status=job.status.value,
            progress=job.progress,
            status_message=job.status_message,
            results=job.results,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            estimated_completion=job.estimated_completion,
            execution_time_seconds=job.execution_time_seconds
        )
        for job in jobs
    ]
    
    return JobListResponse(
        jobs=job_responses,
        total=total,
        limit=limit,
        offset=offset
    )


# =============================================================================
# Market Intelligence Endpoints
# =============================================================================

@router.get("/markets/{market}/summary", response_model=MarketSummary, dependencies=[Depends(verify_api_key)])
async def get_market_summary(market: str, db: Session = Depends(get_db)):
    """
    Get comprehensive market summary for a specific market.
    
    Returns store counts by brand, saturation analysis, and growth opportunities.
    """
    # Validate market
    valid_markets = ["Iowa", "Nebraska", "Nevada", "Idaho"]
    if market not in valid_markets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid market. Must be one of: {', '.join(valid_markets)}"
        )
    
    try:
        # Get total stores in market
        total_result = db.execute(
            text("SELECT COUNT(*) FROM stores WHERE state = :state"),
            {"state": market}
        ).fetchone()
        total_stores = total_result[0] if total_result else 0
        
        # Get stores by brand
        brand_result = db.execute(
            text("""
                SELECT brand, COUNT(*) as count 
                FROM stores 
                WHERE state = :state 
                GROUP BY brand 
                ORDER BY count DESC
            """),
            {"state": market}
        ).fetchall()
        
        stores_by_brand = {row[0]: row[1] for row in brand_result}
        
        # Calculate basic saturation score (simplified)
        # This is a placeholder - would need more sophisticated analysis
        # based on population, area, demographics, etc.
        saturation_score = None
        if total_stores > 0:
            # Very rough estimate: compare to average state density
            # Would need actual population and area data for accuracy
            saturation_score = min(100, (total_stores / 50) * 100)
        
        # Generate simple insights
        growth_opportunities = None
        if total_stores < 20:
            growth_opportunities = "Low market presence - significant expansion opportunity"
        elif total_stores < 50:
            growth_opportunities = "Moderate presence - selective expansion in underserved areas"
        else:
            growth_opportunities = "High presence - focus on optimization and gap filling"
        
        return MarketSummary(
            market=market,
            total_stores=total_stores,
            stores_by_brand=stores_by_brand,
            saturation_score=saturation_score,
            growth_opportunities=growth_opportunities,
            recent_changes=None  # Would need change tracking in database
        )
    
    except Exception as e:
        logger.error(f"Error getting market summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting market summary: {str(e)}")


@router.get("/health", dependencies=[Depends(verify_api_key)])
async def health_check():
    """Health check endpoint for Mission Control integration."""
    return {
        "status": "ok",
        "service": "CSOKi Mission Control Integration API",
        "version": "1.0.0"
    }
