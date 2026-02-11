"""
Seed SCOUT tables with realistic demo data.

Called during startup if tables are empty.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models.scout import ScoutJob, ScoutReport, ScoutDecision

logger = logging.getLogger(__name__)


def seed_scout_data(db: Session) -> bool:
    """Insert mock SCOUT data if tables are empty. Returns True if seeded."""
    if db.query(ScoutJob).count() > 0:
        return False

    now = datetime.now(timezone.utc)

    # ── Jobs ──────────────────────────────────────────────────────────
    jobs = [
        ScoutJob(
            id="scout-job-abc123",
            market="NE",
            status="completed",
            progress=100,
            sites_total=3,
            sites_completed=3,
            config={"criteria": "csoki", "scope": "full"},
            created_at=now - timedelta(days=2),
            started_at=now - timedelta(days=2, hours=-1),
            completed_at=now - timedelta(days=1, hours=18),
        ),
        ScoutJob(
            id="scout-job-def456",
            market="ID",
            status="in_progress",
            progress=67,
            sites_total=3,
            sites_completed=2,
            config={"criteria": "csoki", "scope": "full"},
            created_at=now - timedelta(days=1, hours=14),
            started_at=now - timedelta(days=1, hours=13),
        ),
        ScoutJob(
            id="scout-job-ghi789",
            market="IA",
            status="completed",
            progress=100,
            sites_total=1,
            sites_completed=1,
            config={"criteria": "csoki", "scope": "custom"},
            created_at=now - timedelta(days=3),
            started_at=now - timedelta(days=3),
            completed_at=now - timedelta(days=3, hours=-4),
        ),
    ]

    # ── Reports ───────────────────────────────────────────────────────
    reports = [
        ScoutReport(
            id="rpt-001",
            job_id="scout-job-abc123",
            site_address="4521 Dodge St, Omaha NE",
            market="Omaha Metro",
            latitude=41.2565,
            longitude=-95.9345,
            confidence_score=87,
            feasibility_score=8.5,
            regulatory_score=7.2,
            sentiment_score=8.0,
            growth_score=9.0,
            planning_score=7.5,
            verification_score=8.2,
            strengths=[
                "Strong traffic (28,400 AADT)",
                "Growing population corridor (+12.3% 5yr)",
                "No Verizon corporate within 6.1mi",
                "Cap rate exceeds target by 3.2%",
                "Retail permitted by right (C2 zoning)",
            ],
            flags=[
                {"severity": "medium", "description": "Overlay district requires design review"},
                {"severity": "low", "description": "Traffic count data is 18 months old"},
            ],
            agent_details={
                "feasibility": {
                    "score": 8.5,
                    "label": "Feasibility",
                    "icon": "DollarSign",
                    "details": {
                        "Cap Rate": "11.2% (target: 8%)",
                        "DSCR": "1.34 (min: 1.25)",
                        "Est. Project Cost": "$1,685,000",
                        "Projected NOI": "$189,000",
                        "Meets Lending Criteria": "Yes",
                    },
                    "strengths": ["Strong projected NOI", "Cap rate exceeds target by 3.2%"],
                    "flags": [],
                },
                "regulatory": {
                    "score": 7.2,
                    "label": "Regulatory",
                    "icon": "FileCheck",
                    "details": {
                        "Zoning Code": "C2 (General Commercial)",
                        "Permitted Use": "Retail - by right",
                        "Variance Required": "No",
                        "Est. Timeline": "~4 months",
                    },
                    "strengths": ["Retail permitted by right"],
                    "flags": [{"severity": "medium", "description": "Overlay district requires design review"}],
                },
                "growth": {
                    "score": 9.0,
                    "label": "Growth",
                    "icon": "TrendingUp",
                    "details": {
                        "Pop Growth (5yr)": "+12.3%",
                        "Household Growth": "+8.7%",
                        "Corridor Trend": "Expanding",
                        "Major Developments": "2 within 1mi",
                    },
                    "strengths": ["Rapidly growing corridor", "Multiple anchor developments nearby"],
                    "flags": [],
                },
                "planning": {
                    "score": 7.5,
                    "label": "Planning",
                    "icon": "Building",
                    "details": {
                        "Recent Applications": "3 in area",
                        "Infrastructure Projects": "Road widening Q3 2026",
                        "Competition Pipeline": "No wireless retail applications found",
                    },
                    "strengths": ["No competitor applications in pipeline"],
                    "flags": [],
                },
                "sentiment": {
                    "score": 8.0,
                    "label": "Sentiment",
                    "icon": "MessageSquare",
                    "details": {
                        "Community Reception": "Favorable",
                        "NIMBY Risk": "Low",
                        "News Mentions": "0 negative",
                        "Area Reputation": "Established commercial corridor",
                    },
                    "strengths": ["Established retail area, development-friendly"],
                    "flags": [],
                },
                "verification": {
                    "score": 8.2,
                    "label": "Verification",
                    "icon": "ShieldCheck",
                    "details": {
                        "Data Quality": "8.2/10",
                        "Validations Passed": "12/14",
                        "Validations Failed": "2/14",
                        "Confidence Adjustment": "+0.05",
                    },
                    "strengths": ["High data consistency across sources"],
                    "flags": [{"severity": "low", "description": "Traffic count data is 18 months old"}],
                },
            },
            created_at=now - timedelta(days=1, hours=18),
        ),
        ScoutReport(
            id="rpt-002",
            job_id="scout-job-abc123",
            site_address="1200 N 72nd St, Omaha NE",
            market="Omaha Metro",
            latitude=41.2710,
            longitude=-96.0250,
            confidence_score=72,
            feasibility_score=7.0,
            regulatory_score=6.5,
            sentiment_score=7.5,
            growth_score=8.0,
            planning_score=6.8,
            verification_score=7.5,
            strengths=[
                "Good traffic volume (22,100 AADT)",
                "Median household income $62,400",
            ],
            flags=[
                {"severity": "medium", "description": "Existing Verizon corporate 3.2mi away"},
                {"severity": "low", "description": "Parking may be constrained (18 spaces)"},
            ],
            agent_details={
                "feasibility": {"score": 7.0, "label": "Feasibility", "icon": "DollarSign",
                    "details": {"Cap Rate": "8.9%", "DSCR": "1.28", "Est. Project Cost": "$1,420,000", "Projected NOI": "$126,000"},
                    "strengths": ["Meets minimum lending criteria"], "flags": []},
                "regulatory": {"score": 6.5, "label": "Regulatory", "icon": "FileCheck",
                    "details": {"Zoning Code": "C1 (Neighborhood Commercial)", "Permitted Use": "Retail - conditional", "Est. Timeline": "~6 months"},
                    "strengths": [], "flags": [{"severity": "medium", "description": "Conditional use permit required"}]},
                "growth": {"score": 8.0, "label": "Growth", "icon": "TrendingUp",
                    "details": {"Pop Growth (5yr)": "+9.1%", "Corridor Trend": "Stable-growing"},
                    "strengths": ["Steady population growth"], "flags": []},
                "planning": {"score": 6.8, "label": "Planning", "icon": "Building",
                    "details": {"Recent Applications": "1 in area"},
                    "strengths": [], "flags": []},
                "sentiment": {"score": 7.5, "label": "Sentiment", "icon": "MessageSquare",
                    "details": {"Community Reception": "Neutral-positive"},
                    "strengths": [], "flags": []},
                "verification": {"score": 7.5, "label": "Verification", "icon": "ShieldCheck",
                    "details": {"Data Quality": "7.5/10", "Validations Passed": "11/14"},
                    "strengths": [], "flags": []},
            },
            created_at=now - timedelta(days=1, hours=18),
        ),
        ScoutReport(
            id="rpt-003",
            job_id="scout-job-abc123",
            site_address="800 S Main St, Council Bluffs IA",
            market="Omaha Metro",
            latitude=41.2461,
            longitude=-95.8516,
            confidence_score=65,
            feasibility_score=6.0,
            regulatory_score=5.5,
            sentiment_score=7.0,
            growth_score=7.2,
            planning_score=6.0,
            verification_score=6.8,
            strengths=["Affordable land cost ($12/sqft)"],
            flags=[
                {"severity": "high", "description": "Russell Cellular store 0.8mi away"},
                {"severity": "medium", "description": "Limited frontage (32ft)"},
                {"severity": "low", "description": "Flood zone proximity (Zone X - moderate risk)"},
            ],
            agent_details={
                "feasibility": {"score": 6.0, "label": "Feasibility", "icon": "DollarSign",
                    "details": {"Cap Rate": "7.1%", "Est. Project Cost": "$980,000"},
                    "strengths": ["Low acquisition cost"], "flags": [{"severity": "medium", "description": "Cap rate below 8% target"}]},
                "regulatory": {"score": 5.5, "label": "Regulatory", "icon": "FileCheck",
                    "details": {"Zoning Code": "MU-1 (Mixed Use)", "Est. Timeline": "~8 months"},
                    "strengths": [], "flags": [{"severity": "medium", "description": "Mixed-use zoning may complicate"}]},
                "growth": {"score": 7.2, "label": "Growth", "icon": "TrendingUp",
                    "details": {"Pop Growth (5yr)": "+6.8%"}, "strengths": [], "flags": []},
                "planning": {"score": 6.0, "label": "Planning", "icon": "Building",
                    "details": {}, "strengths": [], "flags": []},
                "sentiment": {"score": 7.0, "label": "Sentiment", "icon": "MessageSquare",
                    "details": {"Community Reception": "Neutral"}, "strengths": [], "flags": []},
                "verification": {"score": 6.8, "label": "Verification", "icon": "ShieldCheck",
                    "details": {"Data Quality": "6.8/10"}, "strengths": [], "flags": []},
            },
            created_at=now - timedelta(days=1, hours=18),
        ),
        ScoutReport(
            id="rpt-004",
            job_id="scout-job-def456",
            site_address="3300 N Eagle Rd, Meridian ID",
            market="Boise",
            latitude=43.6340,
            longitude=-116.3530,
            confidence_score=91,
            feasibility_score=9.2,
            regulatory_score=8.5,
            sentiment_score=9.0,
            growth_score=9.5,
            planning_score=8.8,
            verification_score=9.0,
            strengths=[
                "Exceptional traffic (35,200 AADT)",
                "Fastest-growing corridor in Idaho",
                "No Verizon presence within 8mi",
                "New retail pad site, build-to-suit available",
                "Median income $74,200",
            ],
            flags=[],
            agent_details={
                "feasibility": {"score": 9.2, "label": "Feasibility", "icon": "DollarSign",
                    "details": {"Cap Rate": "12.8%", "DSCR": "1.52", "Est. Project Cost": "$1,950,000", "Projected NOI": "$249,600"},
                    "strengths": ["Excellent projected returns", "Strong DSCR"], "flags": []},
                "regulatory": {"score": 8.5, "label": "Regulatory", "icon": "FileCheck",
                    "details": {"Zoning Code": "C-G (General Commercial)", "Permitted Use": "Retail - by right", "Est. Timeline": "~3 months"},
                    "strengths": ["Retail by right, fast permitting"], "flags": []},
                "growth": {"score": 9.5, "label": "Growth", "icon": "TrendingUp",
                    "details": {"Pop Growth (5yr)": "+18.2%", "Major Developments": "4 within 1mi"},
                    "strengths": ["Top growth corridor in state", "Multiple anchor tenants committed"], "flags": []},
                "planning": {"score": 8.8, "label": "Planning", "icon": "Building",
                    "details": {"Infrastructure Projects": "Interchange improvement 2026"},
                    "strengths": ["Infrastructure investment confirms growth"], "flags": []},
                "sentiment": {"score": 9.0, "label": "Sentiment", "icon": "MessageSquare",
                    "details": {"Community Reception": "Very favorable", "NIMBY Risk": "None"},
                    "strengths": ["Pro-development community"], "flags": []},
                "verification": {"score": 9.0, "label": "Verification", "icon": "ShieldCheck",
                    "details": {"Data Quality": "9.0/10", "Validations Passed": "14/14"},
                    "strengths": ["All data points verified"], "flags": []},
            },
            created_at=now - timedelta(days=1, hours=4),
        ),
        ScoutReport(
            id="rpt-005",
            job_id="scout-job-ghi789",
            site_address="2105 SE Delaware Ave, Ankeny IA",
            market="Des Moines",
            latitude=41.7072,
            longitude=-93.5658,
            confidence_score=58,
            feasibility_score=5.5,
            regulatory_score=5.0,
            sentiment_score=6.5,
            growth_score=6.0,
            planning_score=5.5,
            verification_score=6.0,
            strengths=["Growing suburban market"],
            flags=[
                {"severity": "high", "description": "Cap rate 5.8% - below minimum threshold"},
                {"severity": "high", "description": "Victra store 1.1mi away"},
                {"severity": "medium", "description": "Traffic count below 15K AADT threshold"},
                {"severity": "low", "description": "Lease terms unfavorable (10yr NNN escalation)"},
            ],
            agent_details={
                "feasibility": {"score": 5.5, "label": "Feasibility", "icon": "DollarSign",
                    "details": {"Cap Rate": "5.8%", "Est. Project Cost": "$2,100,000"},
                    "strengths": [], "flags": [{"severity": "high", "description": "Cap rate well below 8% target"}]},
                "regulatory": {"score": 5.0, "label": "Regulatory", "icon": "FileCheck",
                    "details": {"Zoning Code": "PUD", "Est. Timeline": "~10 months"},
                    "strengths": [], "flags": [{"severity": "medium", "description": "PUD requires lengthy approval process"}]},
                "growth": {"score": 6.0, "label": "Growth", "icon": "TrendingUp",
                    "details": {"Pop Growth (5yr)": "+5.2%"}, "strengths": [], "flags": []},
                "planning": {"score": 5.5, "label": "Planning", "icon": "Building",
                    "details": {}, "strengths": [], "flags": []},
                "sentiment": {"score": 6.5, "label": "Sentiment", "icon": "MessageSquare",
                    "details": {"Community Reception": "Neutral"}, "strengths": [], "flags": []},
                "verification": {"score": 6.0, "label": "Verification", "icon": "ShieldCheck",
                    "details": {"Data Quality": "6.0/10"}, "strengths": [], "flags": []},
            },
            created_at=now - timedelta(days=3, hours=-4),
        ),
        ScoutReport(
            id="rpt-006",
            job_id="scout-job-def456",
            site_address="1550 S Entertainment Ave, Boise ID",
            market="Boise",
            latitude=43.5835,
            longitude=-116.2710,
            confidence_score=83,
            feasibility_score=8.0,
            regulatory_score=8.2,
            sentiment_score=8.5,
            growth_score=8.8,
            planning_score=7.5,
            verification_score=8.0,
            strengths=[
                "High-traffic entertainment district",
                "Strong anchor tenants (Target, Costco nearby)",
                "Population density 2.1x state average",
                "Excellent visibility from I-84",
            ],
            flags=[
                {"severity": "low", "description": "Lease rate slightly above market ($28/sqft vs $25 avg)"},
            ],
            agent_details={
                "feasibility": {"score": 8.0, "label": "Feasibility", "icon": "DollarSign",
                    "details": {"Cap Rate": "9.4%", "DSCR": "1.31", "Est. Project Cost": "$1,780,000"},
                    "strengths": ["Solid cap rate"], "flags": []},
                "regulatory": {"score": 8.2, "label": "Regulatory", "icon": "FileCheck",
                    "details": {"Zoning Code": "C-C (Community Commercial)", "Permitted Use": "Retail - by right"},
                    "strengths": ["Retail by right"], "flags": []},
                "growth": {"score": 8.8, "label": "Growth", "icon": "TrendingUp",
                    "details": {"Pop Growth (5yr)": "+14.5%"},
                    "strengths": ["Strong growth corridor"], "flags": []},
                "planning": {"score": 7.5, "label": "Planning", "icon": "Building",
                    "details": {}, "strengths": [], "flags": []},
                "sentiment": {"score": 8.5, "label": "Sentiment", "icon": "MessageSquare",
                    "details": {"Community Reception": "Favorable"},
                    "strengths": ["Popular retail destination"], "flags": []},
                "verification": {"score": 8.0, "label": "Verification", "icon": "ShieldCheck",
                    "details": {"Data Quality": "8.0/10"},
                    "strengths": [], "flags": []},
            },
            created_at=now - timedelta(days=1, hours=4),
        ),
    ]

    # ── Decisions ─────────────────────────────────────────────────────
    decisions = [
        ScoutDecision(
            report_id="rpt-002",
            decision="approved",
            decided_by="Michael",
            decided_at=now - timedelta(days=1, hours=7),
        ),
        ScoutDecision(
            report_id="rpt-003",
            decision="rejected",
            rejection_reason="Too Close to Competition",
            decided_by="Michael",
            decided_at=now - timedelta(days=1, hours=7),
        ),
        ScoutDecision(
            report_id="rpt-005",
            decision="rejected",
            rejection_reason="Financial - Doesn't Pencil",
            decided_by="Michael",
            decided_at=now - timedelta(days=2, hours=14),
        ),
    ]

    # Insert all
    for job in jobs:
        db.add(job)
    db.flush()

    for report in reports:
        db.add(report)
    db.flush()

    for decision in decisions:
        db.add(decision)

    db.commit()
    logger.info(f"Seeded SCOUT data: {len(jobs)} jobs, {len(reports)} reports, {len(decisions)} decisions")
    return True
