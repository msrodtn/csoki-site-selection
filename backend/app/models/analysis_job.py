"""
Analysis Job model for Mission Control integration.

Tracks site analysis requests from Mission Control agents.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum
from app.core.database import Base


class JobStatus(str, Enum):
    """Analysis job status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Analysis job priority values."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisJob(Base):
    """
    Analysis job requested by Mission Control agents.
    
    Tracks site analysis requests, criteria, progress, and results.
    """
    __tablename__ = "analysis_jobs"

    id = Column(String, primary_key=True, index=True)  # Format: "csoki-job-{uuid}"
    
    # Request details
    market = Column(String, nullable=False, index=True)  # Iowa, Nebraska, Nevada, Idaho
    criteria = Column(JSON, nullable=False)  # ["demographics", "competitors", "traffic"]
    priority = Column(SQLEnum(JobPriority), nullable=False, default=JobPriority.MEDIUM, index=True)
    requested_by = Column(String, nullable=False)  # Mission Control agent ID
    callback_url = Column(String, nullable=True)  # Webhook URL for completion notification
    
    # Status tracking
    status = Column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    status_message = Column(String, nullable=True)  # Human-readable status message
    
    # Results (stored as JSON)
    results = Column(JSON, nullable=True)  # Analysis results when completed
    error_message = Column(Text, nullable=True)  # Error details if failed
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Metadata
    estimated_completion = Column(DateTime(timezone=True), nullable=True)
    execution_time_seconds = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<AnalysisJob(id='{self.id}', market='{self.market}', status='{self.status}')>"
