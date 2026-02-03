# CSOKi Site Selection Platform

## Project Overview

An AI-powered site selection dashboard for Cellular Sales (CSOKi) to identify optimal locations for new retail stores. The platform serves executive leadership with strategic market analysis, competitor mapping, and data-driven location recommendations.

### Target Markets
- **Primary:** Iowa & Nebraska
- **Secondary:** Nevada & Idaho

### Core Value Proposition
Enable data-driven expansion decisions by visualizing competitor landscapes, demographic opportunities, and market gaps across target regions.

---

## Current Status (Updated Feb 3, 2026)

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

### Phase 2.5: COMPLETE (Properties For Sale Layer)
- [x] ATTOM Property API integration for commercial property intelligence
- [x] Property search by map viewport bounds
- [x] Opportunity signal detection (tax delinquency, foreclosure, long-term ownership, estate ownership)
- [x] Opportunity scoring (0-100) for each property
- [x] Property type classification (retail, land, office, industrial, mixed_use)
- [x] PropertyInfoCard component with detailed property view
- [x] ReportAll API integration for parcel details (ownership, zoning, boundaries)
- [x] Map layer toggle for Properties For Sale
- [x] Visual distinction: Purple diamonds (opportunities) vs colored circles (active listings)

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
- **External APIs:**
  - Google Maps & Places API (mapping, POIs, autocomplete)
  - ArcGIS GeoEnrichment (demographics)
  - ATTOM Property API (commercial property intelligence, opportunity signals)
  - ReportAll API (parcel details, ownership, zoning, boundaries)

### Stack (Planned for Future Phases)
- **AI/ML:** OpenAI API for conversational features, scikit-learn for scoring models
- **Cache:** Redis for API response caching
- **Additional Data:** QuantumListing, Digsy (free CRE listing platforms)

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
- [x] Competition density heat maps
- [ ] Draw custom analysis areas (Phase 3)
- [ ] Drive-time isochrones (Phase 3)

### 2. Trade Area Analysis
- [x] Click any store → "Analyze Trade Area" button
- [x] Google Places API fetches nearby POIs
- [x] POI categories: Anchors, Quick Service, Restaurants, Retail
- [x] Visual radius circle on map
- [x] POI markers with category colors
- [x] Adjustable radius (0.25, 0.5, 1, 2, 3 miles)
- [x] Auto-refresh when radius changes
- [x] Category visibility toggles
- [x] PDF export with detailed report

### 3. Properties For Sale Layer (NEW - ATTOM Powered)
- [x] Toggle "Properties For Sale" in Map Layers sidebar
- [x] Automatic search when layer enabled (uses map viewport bounds)
- [x] **Opportunity Detection** - Identifies properties likely to sell based on:
  - Tax delinquency
  - Foreclosure/pre-foreclosure status
  - Long-term ownership (15+ years)
  - Estate/trust ownership
  - Undervalued assessments
- [x] **Opportunity Scoring** - 0-100 score based on signal strength
- [x] **Property Types** - Retail, Land, Office, Industrial, Mixed Use
- [x] **Visual Markers**:
  - Purple diamonds = Opportunities (likely to sell, not actively listed)
  - Colored circles = Active listings (color by property type)
- [x] **PropertyInfoCard** on marker click showing:
  - Address, price, size, year built
  - Opportunity signals with explanations
  - Owner name and type
  - "Get Parcel Details" button (ReportAll integration)
- [x] **ReportAll Integration** for detailed parcel info:
  - Parcel ID, zoning, land use
  - Assessed value, acreage
  - Parcel boundary polygon overlay

### 4. City Search with Autocomplete
- [x] Google Places Autocomplete as you type
- [x] Restricted to US cities
- [x] Dropdown with up to 5 suggestions
- [x] Click suggestion → map navigates to location
- [x] Debounced API calls (300ms)

### 5. Map Layers
- [x] FEMA Flood Zones (zoom 12+)
- [x] Traffic (real-time)
- [x] Transit routes
- [x] Parcel Boundaries (zoom 14+, click for info)
- [x] Competition Heat Map
- [x] Business Labels
- [x] Zoning Colors
- [x] Properties For Sale (ATTOM)

### 6. Password Protection
- Simple password gate: `!FiveCo`
- Uses sessionStorage for session persistence

### 7. API Endpoints (Implemented)
```
# Store Locations
GET  /api/v1/locations/              # List all stores with filtering
GET  /api/v1/locations/brands/       # Get available brand names
GET  /api/v1/locations/stats/        # Store count by brand with states
GET  /api/v1/locations/state/{state}/  # Stores in specific state
POST /api/v1/locations/within-bounds/  # Stores in map viewport
POST /api/v1/locations/within-radius/  # Stores within radius

# Trade Area Analysis
POST /api/v1/analysis/trade-area/    # Analyze POIs around location
POST /api/v1/analysis/demographics/  # ArcGIS demographics data
POST /api/v1/analysis/parcel/        # ReportAll parcel lookup
GET  /api/v1/analysis/check-api-key/ # Verify Google Places API key
GET  /api/v1/analysis/check-arcgis-key/    # Verify ArcGIS API key
GET  /api/v1/analysis/check-reportall-key/ # Verify ReportAll API key

# Property Search (ATTOM - NEW)
POST /api/v1/analysis/properties/search/        # Search by radius
POST /api/v1/analysis/properties/search-bounds/ # Search by map bounds
GET  /api/v1/analysis/check-attom-key/          # Verify ATTOM API key

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
- [ ] Integrate additional free listing sources (QuantumListing, Digsy)
- [ ] Team-contributed property flagging (crowdsource from field reps)

### Phase 4: AI Integration
- [ ] Conversational assistant (OpenAI/Anthropic integration)
- [ ] Natural language queries: "Show best opportunities in Des Moines"
- [ ] AI-generated location recommendations
- [ ] Insight summarization

### Phase 5: Reports & Recommendations
- [ ] **Top 5-10 site prospect recommendations** (main goal)
- [ ] Executive dashboard view
- [ ] Enhanced PDF report generation
- [ ] Saved analyses / bookmarks
- [ ] Property watchlist (track opportunities over time)

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
| Map Navigation | Direct (imperative) | Prevents map jumping on re-renders |
| POI Data | Google Places API | Real-time, accurate, comprehensive |
| Search | Google Places Autocomplete | Native integration, US city filtering |
| PDF Export | jsPDF | Client-side generation, no server load |
| Property Data | ATTOM API | Reliable commercial property intelligence, opportunity signals |
| Parcel Data | ReportAll API | Precise boundaries, ownership, zoning details |

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
- `GOOGLE_PLACES_API_KEY` - For trade area analysis, autocomplete
- `ARCGIS_API_KEY` - For demographics data
- `REPORTALL_API_KEY` - For parcel details and boundaries
- `ATTOM_API_KEY` - For commercial property search and opportunity signals

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

8. **Google Maps Libraries**: The `places` and `visualization` libraries are loaded alongside the map. The libraries array must be defined as a constant outside the component to prevent re-render warnings.

9. **Properties For Sale Layer (IMPORTANT)**:
   - Uses ATTOM API for property intelligence (NOT scraping)
   - Previous scraping approach was unreliable - replaced with ATTOM
   - Searches triggered automatically when layer toggled ON
   - Uses map viewport bounds for geographic filtering
   - ReportAll provides parcel details on click (separate from ATTOM)
   - Opportunity signals are calculated from ATTOM data (tax status, ownership duration, foreclosure status, etc.)

### Key Files to Know

**Backend:**
- `backend/app/main.py` - FastAPI app with HTTPS middleware
- `backend/app/core/config.py` - CORS origins, API keys, settings
- `backend/app/api/routes/locations.py` - Store API endpoints
- `backend/app/api/routes/analysis.py` - Trade area, demographics, parcel, and property search endpoints
- `backend/app/services/places.py` - Google Places API integration
- `backend/app/services/arcgis.py` - ArcGIS demographics integration
- `backend/app/services/attom.py` - ATTOM property search and opportunity detection
- `backend/app/services/data_import.py` - CSV import with geocoding

**Frontend:**
- `frontend/src/components/Map/StoreMap.tsx` - Google Maps component with all layers
- `frontend/src/components/Map/PropertyInfoCard.tsx` - Property detail card with opportunity signals
- `frontend/src/components/Map/PropertyLegend.tsx` - Property layer legend
- `frontend/src/components/Analysis/AnalysisPanel.tsx` - Trade area panel with PDF export
- `frontend/src/components/Sidebar/SearchBar.tsx` - City autocomplete search
- `frontend/src/components/Sidebar/MapLayers.tsx` - Layer toggle controls
- `frontend/src/components/Sidebar/StateFilter.tsx` - State toggles with drag reorder
- `frontend/src/components/Auth/PasswordGate.tsx` - Password protection
- `frontend/src/services/api.ts` - API client with axios (includes ATTOM methods)
- `frontend/src/store/useMapStore.ts` - Zustand state (includes mapInstance, navigateTo)
- `frontend/src/types/store.ts` - TypeScript types including PropertyListing, OpportunitySignal

### Data Freshness
- Competitor CSV data can be refreshed by updating files in `/backend/data/competitors/`
- Clear database and restart backend to re-import
- Use `batch_geocode.py` script to geocode new addresses
- Property data from ATTOM is fetched in real-time when layer is enabled

### Brand Colors
```typescript
BRAND_COLORS = {
  csoki: '#E31837',           // Red (CSOKi brand)
  russell_cellular: '#FF6B00', // Orange
  verizon_corporate: '#CD040B', // Verizon Red
  victra: '#000000',           // Black
  tmobile: '#E20074',          // Magenta
  uscellular: '#00A3E0',       // Blue
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

### Property Type Colors
```typescript
PROPERTY_TYPE_COLORS = {
  retail: '#22C55E',      // Green
  land: '#A16207',        // Amber/Brown
  office: '#3B82F6',      // Blue
  industrial: '#6B7280',  // Gray
  mixed_use: '#8B5CF6',   // Purple
}
```

### Opportunity Signal Types
- `tax_delinquent` - Property has delinquent taxes (HIGH strength)
- `distress` - Foreclosure/pre-foreclosure status (HIGH strength)
- `long_term_owner` - Same owner 15+ years (MEDIUM strength)
- `estate_ownership` - Owned by trust or estate (MEDIUM strength)
- `undervalued` - Assessed below market value (MEDIUM strength)
