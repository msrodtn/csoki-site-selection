# CSOKi Migration Plan: External APIs → Local Data

**Date:** 2026-02-18  
**Status:** In Progress

---

## Overview

Migrate CSOKi from paid external APIs (ArcGIS, Attom) to local PostGIS-backed data sources (Census Bureau, county assessor data) using a feature flag system for gradual, safe rollout.

---

## Deployment Sequence

### Phase 1: Deploy Feature Flags at 0% (No User Impact)
1. Deploy `feature_flags.py` with all flags defaulting to `external` mode
2. Add `LOCAL_PROPERTY_DB_URL` and `LOCAL_CENSUS_DB_URL` to production `.env`
3. Verify app starts and behaves identically to pre-migration

### Phase 2: Load Local Data
1. Run `load_census_tracts.py` to populate census tract boundaries (4 states)
2. Import county property/assessor data via `county_data_import.py`
3. Download and upload traffic data for NE, NV, ID via download scripts + `upload-traffic-tilesets.sh`
4. Verify data integrity with spot checks

### Phase 3: Hybrid Rollout (10% → 50% → 100%)
1. Set `LOCAL_DATA_ENABLED=true`, `LOCAL_DATA_PERCENTAGE=10`
2. Monitor for errors, compare results against external APIs
3. Increase to 50%, then 100% as confidence grows
4. At 100%, switch `LOCAL_DATA_MODE=local` to skip percentage checks

### Phase 4: Decommission External APIs
1. Confirm local data covers all use cases
2. Remove ArcGIS/Attom API key requirements (keep as optional fallback)
3. Update documentation

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCAL_DATA_ENABLED` | `false` | Master switch for local data |
| `LOCAL_DATA_MODE` | `external` | `external`, `hybrid`, or `local` |
| `LOCAL_DATA_PERCENTAGE` | `0` | % of requests using local data (hybrid mode) |
| `LOCAL_PROPERTY_DB_URL` | `None` | PostGIS connection for local property data |
| `LOCAL_CENSUS_DB_URL` | `None` | PostGIS connection for local census data |
| `CENSUS_API_KEY` | `None` | Census Bureau API key for ACS/CBP data |

---

## File-Level Checklist

### Core Changes
- [x] `app/core/feature_flags.py` — Feature flag module (validated, working)
- [x] `app/core/config.py` — Add `LOCAL_PROPERTY_DB_URL`, `LOCAL_CENSUS_DB_URL`
- [x] `app/services/census_demographics.py` — Local census demographics service
- [x] `scripts/load_census_tracts.py` — Census tract loader (bugs fixed)

### Data Pipeline
- [x] `scripts/download-nebraska-traffic.py` — NE traffic download (endpoint verified)
- [x] `scripts/download-nevada-traffic.py` — NV traffic download (endpoint verified)
- [x] `scripts/download-idaho-traffic.py` — ID traffic download (endpoint verified)
- [x] `scripts/upload-traffic-tilesets.sh` — Mapbox tileset upload
- [ ] Run download scripts to populate `data/traffic/` with real GeoJSON

### Integration Points
- [ ] `app/api/routes/demographics.py` — Wire feature flag check before calling ArcGIS vs local
- [ ] `app/api/routes/property.py` — Wire feature flag check before calling Attom vs local
- [ ] `app/services/local_property.py` — Local property query service
- [ ] `app/services/county_data_import.py` — County assessor data importer
- [ ] `.env.example` — Add all new environment variables

### Frontend
- [ ] `frontend/src/config/traffic-sources.ts` — Updated with new state tileset configs

---

## Rollback Procedure

**Immediate rollback (< 1 minute):**
```bash
# Disable all local data instantly
LOCAL_DATA_ENABLED=false
# Or call emergency disable endpoint
curl -X POST /api/admin/feature-flags/disable-local
```

**The feature flag module provides:**
- `disable_local_data()` — Resets to external mode immediately
- `enable_local_data(pct)` — Re-enable at specified percentage
- `get_status()` — Full diagnostic of current flag state
- `validate_configuration()` — Check for misconfiguration warnings

**Full rollback:**
1. Set `LOCAL_DATA_MODE=external` in environment
2. Restart application
3. All requests route to external APIs (ArcGIS/Attom)
4. No data loss — local data remains in PostGIS for future use
