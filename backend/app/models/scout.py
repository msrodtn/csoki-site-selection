"""
SCOUT models for AI-powered site analysis.

Tables:
  - scout_jobs: Analysis job tracking (market scan requests)
  - scout_reports: Individual site analysis results from agents
  - scout_decisions: Human feedback on reports (approve/reject/flag)
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class ScoutJob(Base):
    """An analysis job launched against a market."""

    __tablename__ = "scout_jobs"

    id = Column(String, primary_key=True)
    market = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Float, default=0)
    sites_total = Column(Integer, default=0)
    sites_completed = Column(Integer, default=0)
    config = Column(JSONB)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<ScoutJob(id={self.id}, market={self.market}, status={self.status})>"


class ScoutReport(Base):
    """Analysis result for a single candidate site."""

    __tablename__ = "scout_reports"

    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("scout_jobs.id"), nullable=False, index=True)
    site_address = Column(Text, nullable=False)
    market = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)

    # Scores
    confidence_score = Column(Float)
    feasibility_score = Column(Float)
    regulatory_score = Column(Float)
    sentiment_score = Column(Float)
    growth_score = Column(Float)
    planning_score = Column(Float)
    verification_score = Column(Float)

    # Structured data
    strengths = Column(JSONB)
    flags = Column(JSONB)
    agent_details = Column(JSONB)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ScoutReport(id={self.id}, address={self.site_address}, confidence={self.confidence_score})>"


class ScoutDecision(Base):
    """Human decision on a scout report."""

    __tablename__ = "scout_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, ForeignKey("scout_reports.id"), nullable=False, index=True)
    decision = Column(String(20), nullable=False)
    rejection_reason = Column(String(255))
    notes = Column(Text)
    decided_by = Column(String(100))
    decided_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ScoutDecision(id={self.id}, report={self.report_id}, decision={self.decision})>"
