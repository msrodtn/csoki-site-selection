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

### Phase 2: COMPLETE
- [x] Trade Area Analysis with Google Places API
- [x] POI categorization (Anchors, Quick Service, Restaurants, Retail)
- [x] Adjustable analysis radius (0.25, 0.5, 1, 2, 3 miles)
- [x] Auto-refresh analysis on radius change
- [x] PDF export of analysis reports
- [x] City autocomplete search (Google Places Autocomplete)
- [x] Target market state toggles with drag-to-reorder
- [x] Store breakdown by brand per state (expandable)
- [x] Map stability fixes (direct navigation pattern)

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
- **External APIs:** Google Maps, Google Places API

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
- [x] Color-coded markers by brand (larger than POI markers)
- [x] Store info popups on click (address, brand, analyze button)
- [x] Target market state filtering with toggle visibility
- [x] Drag-to-reorder state priority in sidebar
- [x] Store breakdown by brand per state (expandable chevron)
- [ ] Heat maps showing competition density (Phase 3)
- [ ] Draw custom analysis areas (Phase 3)
- [ ] Drive-time isochrones (Phase 3)

### 2. Trade Area Analysis (NEW)
- [x] Click any store → "Analyze Trade Area" button
- [x] Google Places API fetches nearby POIs
- [x] POI categories: Anchors, Quick Service, Restaurants, Retail
- [x] Visual radius circle on map
- [x] POI markers with category colors
- [x] Adjustable radius (0.25, 0.5, 1, 2, 3 miles)
- [x] Auto-refresh when radius changes
- [x] Category visibility toggles
- [x] PDF export with detailed report

### 3. City Search with Autocomplete (NEW)
- [x] Google Places Autocomplete as you type
- [x] Restricted to US cities
- [x] Dropdown with up to 5 suggestions
- [x] Click suggestion → map navigates to location
- [x] Debounced API calls (300ms)

### 4. Password Protection
- Simple password gate: `!FiveCo`
- Uses sessionStorage for session persistence

### 5. API Endpoints (Implemented)
```
# Store Locations
GET  /api/v1/locations/              # List all stores with filtering
GET  /api/v1/locations/brands/       # Get available brand names
GET  /api/v1/locations/stats/        # Store count by brand with states
GET  /api/v1/locations/state/{state}/  # Stores in specific state
POST /api/v1/locations/within-bounds/  # Stores in map viewport
POST /api/v1/locations/within-radius/  # Stores within radius

# Trade Area Analysis (NEW)
POST /api/v1/analysis/trade-area/    # Analyze POIs around location
GET  /api/v1/analysis/check-api-key/ # Verify Google Places API key

# Health
GET  /health                         # Health check
```

---

## Remaining Development Phases

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
- [ ] Census API integration for demographics

### Phase 4: AI Integration
- [ ] Conversational assistant (OpenAI integration)
- [ ] Natural language queries: "Show best opportunities in Des Moines"
- [ ] AI-generated location recommendations
- [ ] Insight summarization

### Phase 5: Reports & Recommendations
- [ ] **Top 5-10 site prospect recommendations** (main goal)
- [ ] Executive dashboard view
- [ ] Enhanced PDF report generation
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
| Map Navigation | Direct (imperative) | Prevents map jumping on re-renders (see below) |
| POI Data | Google Places API | Real-time, accurate, comprehensive |
| Search | Google Places Autocomplete | Native integration, US city filtering |
| PDF Export | jsPDF | Client-side generation, no server load |

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
- `GOOGLE_PLACES_API_KEY` - For trade area analysis

**Frontend:**
- `VITE_API_URL` - Backend URL
- `VITE_GOOGLE_MAPS_API_KEY` - Google Maps API key (also enables Places)

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

7. **Map Navigation Pattern (IMPORTANT)**:
   - The map uses **direct/imperative navigation** via `navigateTo()` in Zustand
   - The `GoogleMap` component is **uncontrolled** (no `center` or `zoom` props)
   - Initial position is set only in `onLoad` callback
   - This prevents the map from jumping when clicking markers or during re-renders
   - Previous attempts using reactive state (`setViewport` + useEffect) caused instability

8. **Google Maps Libraries**: The `places` library is loaded alongside the map for autocomplete functionality. The libraries array must be defined as a constant outside the component to prevent re-render warnings.

### Key Files to Know

**Backend:**
- `backend/app/main.py` - FastAPI app with HTTPS middleware
- `backend/app/core/config.py` - CORS origins, API keys, settings
- `backend/app/api/routes/locations.py` - Store API endpoints
- `backend/app/api/routes/analysis.py` - Trade area analysis endpoint
- `backend/app/services/places.py` - Google Places API integration
- `backend/app/services/data_import.py` - CSV import with geocoding

**Frontend:**
- `frontend/src/components/Map/StoreMap.tsx` - Google Maps component (uncontrolled)
- `frontend/src/components/Analysis/AnalysisPanel.tsx` - Trade area panel with PDF export
- `frontend/src/components/Sidebar/SearchBar.tsx` - City autocomplete search
- `frontend/src/components/Sidebar/StateFilter.tsx` - State toggles with drag reorder
- `frontend/src/components/Auth/PasswordGate.tsx` - Password protection
- `frontend/src/services/api.ts` - API client with axios (includes analysisApi)
- `frontend/src/store/useMapStore.ts` - Zustand state (includes mapInstance, navigateTo)
- `frontend/src/types/store.ts` - TypeScript types including POI categories

### Data Freshness
- Competitor CSV data can be refreshed by updating files in `/backend/data/competitors/`
- Clear database and restart backend to re-import
- Use `batch_geocode.py` script to geocode new addresses

### Brand Colors
```typescript
BRAND_COLORS = {
  csoki: '#E31837',           // Red (CSOKi brand)
  russell_cellular: '#00A651', // Green
  verizon_corporate: '#CD040B', // Verizon Red
  victra: '#000000',           // Black
  tmobile: '#E20074',          // Magenta
  uscellular: '#00529B',       // Blue
}
```

### POI Category Colors
```typescript
POI_CATEGORY_COLORS = {
  anchors: '#8B5CF6',      // Purple
  quick_service: '#F59E0B', // Amber
  restaurants: '#10B981',   // Emerald
  retail: '#3B82F6',        // Blue
}
```
