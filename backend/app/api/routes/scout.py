"""
SCOUT API routes.

Endpoints for managing analysis jobs, site reports, decisions, and dashboard stats.
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.core.database import get_db
from app.models.scout import ScoutJob, ScoutReport, ScoutDecision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scout", tags=["scout"])


# =============================================================================
# Request / Response Schemas
# =============================================================================

# --- Jobs ---

class JobCreate(BaseModel):
    id: str
    market: str
    config: Optional[dict] = None

class JobUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[float] = None
    sites_total: Optional[int] = None
    sites_completed: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class JobResponse(BaseModel):
    id: str
    market: str
    status: str
    progress: float
    sites_total: int
    sites_completed: int
    config: Optional[dict]
    error: Optional[str]
    created_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Reports ---

class ReportCreate(BaseModel):
    id: str
    job_id: str
    site_address: str
    market: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence_score: Optional[float] = None
    feasibility_score: Optional[float] = None
    regulatory_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    growth_score: Optional[float] = None
    planning_score: Optional[float] = None
    verification_score: Optional[float] = None
    strengths: Optional[list] = None
    flags: Optional[list] = None
    agent_details: Optional[dict] = None

class ReportResponse(BaseModel):
    id: str
    job_id: str
    site_address: str
    market: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    confidence_score: Optional[float]
    feasibility_score: Optional[float]
    regulatory_score: Optional[float]
    sentiment_score: Optional[float]
    growth_score: Optional[float]
    planning_score: Optional[float]
    verification_score: Optional[float]
    strengths: Optional[list]
    flags: Optional[list]
    agent_details: Optional[dict]
    created_at: Optional[datetime]
    decision_status: Optional[str] = None

    class Config:
        from_attributes = True


# --- Decisions ---

class DecisionCreate(BaseModel):
    report_id: str
    decision: str
    rejection_reason: Optional[str] = None
    notes: str
    decided_by: Optional[str] = None

class DecisionResponse(BaseModel):
    id: int
    report_id: str
    decision: str
    rejection_reason: Optional[str]
    notes: Optional[str]
    decided_by: Optional[str]
    decided_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Stats ---

class StatsResponse(BaseModel):
    total_reports: int
    total_jobs: int
    active_jobs: int
    avg_confidence: Optional[float]
    approval_rate: Optional[float]
    decisions_count: int


# =============================================================================
# Job Endpoints
# =============================================================================

@router.get("/jobs/", response_model=List[JobResponse])
def list_jobs(
    status: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all SCOUT jobs with optional filters."""
    query = db.query(ScoutJob)
    if status:
        query = query.filter(ScoutJob.status == status)
    if market:
        query = query.filter(ScoutJob.market == market)
    return query.order_by(ScoutJob.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/jobs/", response_model=JobResponse)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    """Create a new analysis job (called by SCOUT agent or frontend)."""
    existing = db.query(ScoutJob).filter(ScoutJob.id == body.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Job ID already exists")

    job = ScoutJob(
        id=body.id,
        market=body.market,
        status="pending",
        progress=0,
        sites_total=0,
        sites_completed=0,
        config=body.config,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Created SCOUT job {job.id} for market {job.market}")
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get a single job by ID."""
    job = db.query(ScoutJob).filter(ScoutJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(job_id: str, body: JobUpdate, db: Session = Depends(get_db)):
    """Update job status/progress (called by SCOUT agent during analysis)."""
    job = db.query(ScoutJob).filter(ScoutJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    logger.info(f"Updated SCOUT job {job.id}: status={job.status}, progress={job.progress}")
    return job


# =============================================================================
# Report Endpoints
# =============================================================================

@router.get("/reports/", response_model=List[ReportResponse])
def list_reports(
    job_id: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0, le=100),
    market: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List site reports with optional filters."""
    query = db.query(ScoutReport)
    if job_id:
        query = query.filter(ScoutReport.job_id == job_id)
    if min_confidence is not None:
        query = query.filter(ScoutReport.confidence_score >= min_confidence)
    if market:
        query = query.filter(ScoutReport.market == market)

    reports = query.order_by(ScoutReport.confidence_score.desc()).offset(offset).limit(limit).all()

    # Attach decision status to each report
    result = []
    for report in reports:
        resp = ReportResponse.model_validate(report)
        decision = (
            db.query(ScoutDecision)
            .filter(ScoutDecision.report_id == report.id)
            .order_by(ScoutDecision.decided_at.desc())
            .first()
        )
        resp.decision_status = decision.decision if decision else "pending"
        result.append(resp)

    return result


@router.post("/reports/", response_model=ReportResponse)
def create_report(body: ReportCreate, db: Session = Depends(get_db)):
    """Submit a site analysis report (called by SCOUT agent)."""
    existing = db.query(ScoutReport).filter(ScoutReport.id == body.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Report ID already exists")

    report = ScoutReport(
        id=body.id,
        job_id=body.job_id,
        site_address=body.site_address,
        market=body.market,
        latitude=body.latitude,
        longitude=body.longitude,
        confidence_score=body.confidence_score,
        feasibility_score=body.feasibility_score,
        regulatory_score=body.regulatory_score,
        sentiment_score=body.sentiment_score,
        growth_score=body.growth_score,
        planning_score=body.planning_score,
        verification_score=body.verification_score,
        strengths=body.strengths,
        flags=body.flags,
        agent_details=body.agent_details,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info(f"Created SCOUT report {report.id} for {report.site_address}")

    resp = ReportResponse.model_validate(report)
    resp.decision_status = "pending"
    return resp


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, db: Session = Depends(get_db)):
    """Get full report detail by ID."""
    report = db.query(ScoutReport).filter(ScoutReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    resp = ReportResponse.model_validate(report)
    decision = (
        db.query(ScoutDecision)
        .filter(ScoutDecision.report_id == report_id)
        .order_by(ScoutDecision.decided_at.desc())
        .first()
    )
    resp.decision_status = decision.decision if decision else "pending"
    return resp


# =============================================================================
# Decision Endpoints
# =============================================================================

@router.post("/decisions/", response_model=DecisionResponse)
def submit_decision(body: DecisionCreate, db: Session = Depends(get_db)):
    """Submit a human decision on a report (approve/reject/flag)."""
    if body.decision not in ("approved", "rejected", "flagged"):
        raise HTTPException(status_code=400, detail="decision must be 'approved', 'rejected', or 'flagged'")

    if not body.notes or len(body.notes.strip()) < 10:
        raise HTTPException(status_code=400, detail="Feedback notes are required (minimum 10 characters)")

    # Verify report exists
    report = db.query(ScoutReport).filter(ScoutReport.id == body.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    decision = ScoutDecision(
        report_id=body.report_id,
        decision=body.decision,
        rejection_reason=body.rejection_reason,
        notes=body.notes,
        decided_by=body.decided_by,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    logger.info(f"Decision on report {body.report_id}: {body.decision} by {body.decided_by}")
    return decision


@router.get("/decisions/", response_model=List[DecisionResponse])
def list_decisions(
    report_id: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all decisions with optional filters."""
    query = db.query(ScoutDecision)
    if report_id:
        query = query.filter(ScoutDecision.report_id == report_id)
    if decision:
        query = query.filter(ScoutDecision.decision == decision)
    return query.order_by(ScoutDecision.decided_at.desc()).offset(offset).limit(limit).all()


@router.get("/decisions/export/")
def export_decisions(
    since: Optional[datetime] = Query(None, description="Filter decisions since this ISO datetime"),
    db: Session = Depends(get_db),
):
    """Export decisions with full report context for SCOUT agent learning loop.

    SCOUT agent polls this endpoint to get human feedback for prompt injection.
    Use ?since=<ISO datetime> for incremental polling.
    """
    query = db.query(ScoutDecision)
    if since:
        query = query.filter(ScoutDecision.decided_at >= since)

    decisions = query.order_by(ScoutDecision.decided_at.desc()).all()

    result = []
    for d in decisions:
        report = db.query(ScoutReport).filter(ScoutReport.id == d.report_id).first()
        entry = {
            "decision_id": d.id,
            "decision": d.decision,
            "notes": d.notes,
            "rejection_reason": d.rejection_reason,
            "decided_by": d.decided_by,
            "decided_at": d.decided_at.isoformat() if d.decided_at else None,
            "report": None,
        }
        if report:
            entry["report"] = {
                "id": report.id,
                "site_address": report.site_address,
                "market": report.market,
                "confidence_score": report.confidence_score,
                "feasibility_score": report.feasibility_score,
                "regulatory_score": report.regulatory_score,
                "sentiment_score": report.sentiment_score,
                "growth_score": report.growth_score,
                "strengths": report.strengths,
                "flags": report.flags,
                "agent_details": report.agent_details,
            }
        result.append(entry)

    return result


# =============================================================================
# Stats Endpoint
# =============================================================================

@router.get("/stats/", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Dashboard metrics for the SCOUT overview."""
    total_reports = db.query(ScoutReport).count()
    total_jobs = db.query(ScoutJob).count()
    active_jobs = db.query(ScoutJob).filter(
        ScoutJob.status.in_(["pending", "in_progress"])
    ).count()

    avg_confidence = db.query(
        sqlfunc.avg(ScoutReport.confidence_score)
    ).scalar()

    decisions_count = db.query(ScoutDecision).count()
    approved_count = db.query(ScoutDecision).filter(
        ScoutDecision.decision == "approved"
    ).count()

    approval_rate = None
    if decisions_count > 0:
        approval_rate = round((approved_count / decisions_count) * 100, 1)

    return StatsResponse(
        total_reports=total_reports,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        avg_confidence=round(avg_confidence, 1) if avg_confidence else None,
        approval_rate=approval_rate,
        decisions_count=decisions_count,
    )
