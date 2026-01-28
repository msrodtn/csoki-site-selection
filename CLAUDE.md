# CSOKi Site Selection Platform

## Project Overview

An AI-powered site selection dashboard for Cellular Sales (CSOKi) to identify optimal locations for new retail stores. The platform serves executive leadership with strategic market analysis, competitor mapping, and data-driven location recommendations.

### Target Markets
- **Primary:** Iowa & Nebraska
- **Secondary:** Nevada & Idaho

### Core Value Proposition
Enable data-driven expansion decisions by visualizing competitor landscapes, demographic opportunities, and market gaps across target regions.

---

## Current Status (Updated Jan 28, 2026)

### Phase 1: COMPLETE
- [x] Project scaffolding (backend + frontend)
- [x] Database setup with PostGIS on Railway
- [x] Import all 6 competitor datasets (1,918 stores total)
- [x] Geocode addresses using US Census Bureau Batch Geocoder (88% success - 1,688 stores)
- [x] Google Maps visualization with competitor pins
- [x] Brand toggle filters (6 competitors)
- [x] Market/state selection
- [x] Password protection (`!FiveCo`)
- [x] Production deployment on Railway with custom domain

### Live URLs
- **Dashboard:** https://dashboard.fivecodevelopment.com
- **Backend API:** https://backend-production-cf26.up.railway.app
- **API Docs:** https://backend-production-cf26.up.railway.app/docs

---

## Technical Architecture

### Stack (Implemented)
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, GeoAlchemy2
- **Frontend:** React 18, TypeScript, Google Maps API, TailwindCSS, Zustand
- **Database:** PostgreSQL 15 with PostGIS (Railway hosted)
- **Hosting:** Railway (backend + frontend + PostgreSQL)
- **Domain:** GoDaddy DNS → Railway

### Stack (Planned for Future Phases)
- **AI/ML:** OpenAI API for conversational features, scikit-learn for scoring models
- **Cache:** Redis for API response caching
- **Demographics:** US Census API

---

## Data Architecture

### Competitor Data (All Complete)
| Source | Records | Geocoded | Status |
|--------|---------|----------|--------|
| CSOKi (Cellular Sales) | 860 | 749 | ✅ Complete |
| Russell Cellular | 686 | 593 | ✅ Complete |
| T-Mobile | 210 | 198 | ✅ Complete |
| US Cellular | 85 | 79 | ✅ Complete |
| Verizon Corporate | 40 | 38 | ✅ Complete |
| Victra | 37 | 31 | ✅ Complete |
| **Total** | **1,918** | **1,688** | **88% geocoded** |

### Store Data Schema (Implemented)
```sql
CREATE TABLE stores (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(50) NOT NULL,
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    postal_code VARCHAR(10),
    latitude FLOAT,
    longitude FLOAT,
    location GEOGRAPHY(POINT, 4326),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stores_brand_state ON stores(brand, state);
-- GeoAlchemy2 auto-creates spatial index for location column
```

### CSV Data Files (Pre-geocoded)
Located in `/backend/data/competitors/`:
- `csoki_all_stores.csv` - 860 stores
- `russell_cellular_all_stores.csv` - 686 stores
- `tmobile_stores.csv` - 210 stores
- `uscellular_stores.csv` - 85 stores
- `verizon_corporate_stores.csv` - 40 stores
- `victra_stores.csv` - 37 stores

---

## Implemented Features

### 1. Interactive Map Dashboard
- [x] Google Maps with 1,688 geocoded store locations
- [x] Multi-layer competitor visualization (toggle by brand)
- [x] Color-coded markers by brand
- [x] Store info popups on click (address, brand)
- [x] Market/state filtering (IA, NE, NV, ID)
- [ ] Heat maps showing competition density (Phase 3)
- [ ] Draw custom analysis areas (Phase 3)
- [ ] Drive-time isochrones (Phase 3)

### 2. Password Protection
- Simple password gate: `!FiveCo`
- Uses sessionStorage for session persistence

### 3. API Endpoints (Implemented)
```
GET  /api/v1/locations/           # List all stores with filtering
GET  /api/v1/locations/brands/    # Get available brand names
GET  /api/v1/locations/stats/     # Store count by brand with states
GET  /api/v1/locations/state/{state}/  # Stores in specific state
POST /api/v1/locations/within-bounds/  # Stores in map viewport
POST /api/v1/locations/within-radius/  # Stores within radius
GET  /health                      # Health check
```

---

## Remaining Development Phases

### Phase 2: Data Enrichment
- [ ] Census API integration for demographics (population, income, age)
- [ ] Demographic overlay layers on map
- [ ] Zip code / city search functionality
- [ ] Population density visualization

### Phase 3: Analysis Tools (Priority)
- [ ] Location scoring algorithm:
  - Competition Factor (30%): Distance to competitors, density
  - Demographics (25%): Population, income, age distribution
  - Traffic (20%): Foot traffic, retail activity
  - Accessibility (15%): Road proximity, visibility
  - Market Gaps (10%): Underserved areas
- [ ] Draw-to-analyze tool (custom polygons)
- [ ] Drive-time radius analysis (5/10/15 min isochrones)
- [ ] Competition density heat maps

### Phase 4: AI Integration
- [ ] Conversational assistant (OpenAI integration)
- [ ] Natural language queries: "Show best opportunities in Des Moines"
- [ ] AI-generated location recommendations
- [ ] Insight summarization

### Phase 5: Reports & Recommendations
- [ ] **Top 5-10 site prospect recommendations** (main goal)
- [ ] Executive dashboard view
- [ ] PDF report generation
- [ ] Saved analyses / bookmarks

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Map Library | Google Maps API | User preference, familiar interface |
| Geocoding | US Census Batch Geocoder | Free, no API key required, good accuracy |
| Hosting | Railway | Easy deployment, PostgreSQL + PostGIS support |
| State Management | Zustand | Simple, lightweight, React-friendly |
| API Client | Axios + React Query | Caching, loading states, error handling |
| Password Auth | Simple sessionStorage | MVP approach, no user management needed yet |

---

## Deployment

### Railway Services
- **backend**: FastAPI app with PostGIS connection
- **frontend**: React app served via nginx
- **PostgreSQL**: Railway-managed with PostGIS extension

### Environment Variables (Railway)
**Backend:**
- `DATABASE_URL` - Auto-provided by Railway PostgreSQL
- `CORS_ORIGINS` - Includes production frontend domains

**Frontend:**
- `VITE_API_URL` - Backend URL
- `VITE_GOOGLE_MAPS_API_KEY` - Google Maps API key

### Manual Deployment
```bash
# From project root
cd backend && railway service backend && railway up
cd ../frontend && railway service frontend && railway up
```

---

## Notes for Claude

### Important Implementation Details

1. **API URL trailing slashes**: All frontend API calls use trailing slashes (`/locations/`) because FastAPI routes are defined with trailing slashes

2. **HTTPS Middleware**: Backend uses custom `HTTPSRedirectMiddleware` to handle X-Forwarded-Proto header from Railway proxy

3. **CORS Configuration**: Production domains added to `backend/app/core/config.py`:
   - https://dashboard.fivecodevelopment.com
   - https://frontend-production-12b6.up.railway.app

4. **Database Auto-Seeding**: On startup, if database is empty, `main.py` automatically imports all CSV files from `/data/competitors/`

5. **Geocoding**: Pre-geocoded CSV files include `latitude` and `longitude` columns. The batch geocoder script is at `/backend/scripts/batch_geocode.py`

6. **Brand Filter**: Uses Array.includes() instead of Set.has() for reliable checking after serialization

### Key Files to Know
- `backend/app/main.py` - FastAPI app with HTTPS middleware
- `backend/app/core/config.py` - CORS origins, settings
- `backend/app/api/routes/locations.py` - All store API endpoints
- `backend/app/services/data_import.py` - CSV import with geocoding
- `frontend/src/components/Map/StoreMap.tsx` - Google Maps component
- `frontend/src/components/Auth/PasswordGate.tsx` - Password protection
- `frontend/src/services/api.ts` - API client with axios
- `frontend/src/store/useMapStore.ts` - Zustand state for map

### Data Freshness
- Competitor CSV data can be refreshed by updating files in `/backend/data/competitors/`
- Clear database and restart backend to re-import
- Use `batch_geocode.py` script to geocode new addresses
