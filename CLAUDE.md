# CSOKi Site Selection Platform

## Project Overview

An AI-powered site selection dashboard for Cellular Sales (CSOKi) to identify optimal locations for new Verizon retail stores. The platform serves executive leadership with strategic market analysis, competitor mapping, property opportunity detection, and data-driven location recommendations.

### Target Markets
- **Primary:** Iowa & Nebraska
- **Secondary:** Nevada & Idaho
- **Coverage:** All 50 US states for competitor mapping and demographic data

### Core Value Proposition
Enable data-driven expansion decisions by visualizing competitor landscapes, demographic opportunities, property opportunities, and market gaps across target regions.

---

## Current Status (Updated Feb 2026)

### Phase 1: COMPLETE
- [x] Project scaffolding (FastAPI + React/Vite)
- [x] Database setup with PostGIS on Railway
- [x] Import all 6 competitor datasets (1,918 stores, 1,688 geocoded)
- [x] Mapbox GL JS map with competitor pins (brand-colored markers)
- [x] Brand toggle filters, state filtering, drag-to-reorder states
- [x] Password protection (`!FiveCo`)
- [x] Production deployment on Railway

### Phase 2: COMPLETE
- [x] Trade area analysis (Google Places & Mapbox Places POI discovery)
- [x] Demographics integration (ArcGIS GeoEnrichment, 1/3/5 mi radii)
- [x] Adjustable analysis radius (0.25, 0.5, 1, 2, 3 miles)
- [x] PDF export of analysis reports
- [x] City autocomplete search (Mapbox Search Box)
- [x] Map layers: FEMA Flood Zones, Traffic, Transit, Census Tracts, Parcels, Zoning, Buildings
- [x] Competition density heat maps
- [x] 3D building layer with interactive click

### Phase 2.5: COMPLETE (Properties & Listings)
- [x] ATTOM Property API integration (commercial property intelligence, opportunity signals)
- [x] ReportAll API integration (parcel details, ownership, zoning, boundaries)
- [x] Crexi listing integration (automated CSV export with browser automation)
- [x] Team-contributed property flagging (crowdsource from field reps)
- [x] URL-based listing import (manual listing entry)

### Phase 3: MOSTLY COMPLETE
- [x] CSOKi Opportunities layer (ATTOM-filtered, Verizon-family proximity)
- [x] Opportunity scoring & ranking (empty parcels, vacant, absentee, tax liens, etc.)
- [x] Drive-time isochrones (Mapbox Isochrone API)
- [x] Mapbox Matrix API for distance/time calculations
- [x] Competitor accessibility analysis (drive-time to nearby competitors)
- [x] StreetLight traffic counts integration
- [x] Boundary overlays via Mapbox vector tilesets (counties, cities, ZCTAs, census tracts)
- [x] County choropleth with demographic metrics (population, income, density)
- [x] Nearest competitor analysis
- [ ] Location scoring algorithm (planned)
- [ ] Draw-to-analyze tool (planned)

### Live URLs
- **Dashboard:** https://dashboard.fivecodevelopment.com
- **Backend API:** https://backend-production-cf26.up.railway.app
- **API Docs:** https://backend-production-cf26.up.railway.app/docs

---

## Technical Architecture

### Stack
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, GeoAlchemy2
- **Frontend:** React 18, TypeScript, Vite, TailwindCSS
- **Maps:** Mapbox GL JS (react-map-gl)
- **State Management:** Zustand
- **API Client:** React Query + Axios
- **Database:** PostgreSQL 15 with PostGIS (Railway hosted)
- **Hosting:** Railway (backend + frontend + PostgreSQL)
- **Domain:** GoDaddy DNS -> Railway

### External APIs
| API | Purpose |
|-----|---------|
| Mapbox GL JS | Map rendering, search, isochrones, matrix, tilesets |
| Google Places | POI discovery (trade area analysis) |
| ArcGIS GeoEnrichment | Demographics (population, income, spending) |
| ATTOM Property | Commercial property intelligence, opportunity signals |
| ReportAll | Parcel details, ownership, zoning, boundaries |
| StreetLight | Traffic count data |
| Crexi | Commercial listing data (browser automation) |
| Tavily | AI-powered property search (legacy) |

### Project Structure
```
csoki-site-selection/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py          # Router registration
│   │   │   └── routes/
│   │   │       ├── analysis.py      # Trade area, demographics, properties, matrix, boundaries
│   │   │       ├── locations.py     # Store CRUD & spatial queries
│   │   │       ├── opportunities.py # CSOKi opportunity search & scoring
│   │   │       ├── listings.py      # Crexi/LoopNet listing scraping
│   │   │       ├── team_properties.py # Team-flagged properties
│   │   │       └── traffic.py       # Traffic count data by state
│   │   ├── core/
│   │   │   ├── config.py            # Environment settings, CORS, API keys
│   │   │   └── database.py          # PostgreSQL/PostGIS connection
│   │   ├── models/
│   │   │   ├── store.py             # Store/competitor locations
│   │   │   ├── team_property.py     # Team-flagged properties
│   │   │   └── scraped_listing.py   # Scraped real estate listings
│   │   ├── services/
│   │   │   ├── arcgis.py            # ArcGIS GeoEnrichment
│   │   │   ├── attom.py             # ATTOM property search & opportunities
│   │   │   ├── crexi_automation.py  # Crexi browser automation
│   │   │   ├── crexi_parser.py      # Crexi CSV parsing
│   │   │   ├── data_import.py       # CSV import with geocoding
│   │   │   ├── geocoding.py         # Geocoding services
│   │   │   ├── listing_scraper.py   # Listing scraper engine
│   │   │   ├── mapbox_datasets.py   # Mapbox Datasets API
│   │   │   ├── mapbox_isochrone.py  # Mapbox Isochrone API
│   │   │   ├── mapbox_matrix.py     # Mapbox Matrix API
│   │   │   ├── mapbox_places.py     # Mapbox Places POI search
│   │   │   ├── places.py            # Google Places POI search
│   │   │   ├── property_search.py   # Property search logic
│   │   │   ├── streetlight.py       # StreetLight traffic API
│   │   │   └── url_import.py        # Import listings from URLs
│   │   ├── utils/
│   │   │   └── geo.py               # Shared haversine utility
│   │   └── main.py                  # FastAPI app, middleware, startup
│   ├── data/competitors/            # Geocoded store CSVs (6 brands)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   │   ├── MapboxMap.tsx         # Main map component (2600+ lines)
│   │   │   │   ├── MapboxSearchBar.tsx   # Places search autocomplete
│   │   │   │   ├── MapStyleSwitcher.tsx  # Map style selector
│   │   │   │   ├── PropertyInfoCard.tsx  # Property detail card
│   │   │   │   ├── PropertySearchPanel.tsx
│   │   │   │   ├── TeamPropertyForm.tsx  # Flag properties from field
│   │   │   │   ├── CrexiLoader.tsx       # Crexi listing loader
│   │   │   │   ├── URLImportPanel.tsx    # Import listings from URLs
│   │   │   │   ├── IsochroneControl.tsx  # Drive-time isochrone controls
│   │   │   │   ├── QuickStatsBar.tsx     # Quick statistics bar
│   │   │   │   ├── DraggableParcelInfo.tsx
│   │   │   │   ├── *Legend.tsx           # FEMALegend, HeatMapLegend, etc.
│   │   │   │   ├── controls/            # NavigationControl, GeolocateControl
│   │   │   │   └── layers/              # BuildingLayer, POILayer, etc.
│   │   │   ├── Analysis/
│   │   │   │   ├── AnalysisPanel.tsx     # Trade area panel (1000+ lines)
│   │   │   │   ├── ComparePanel.tsx      # Location comparison
│   │   │   │   ├── CompetitorAccessPanel.tsx
│   │   │   │   ├── ReportModal.tsx
│   │   │   │   └── TradeAreaReport.tsx   # PDF report generation
│   │   │   ├── Sidebar/
│   │   │   │   ├── Sidebar.tsx           # Main sidebar container
│   │   │   │   ├── BrandFilter.tsx       # Brand toggle filters
│   │   │   │   ├── MapLayers.tsx         # Layer toggle controls
│   │   │   │   └── StateFilter.tsx       # State toggles, drag reorder
│   │   │   └── Auth/
│   │   │       └── PasswordGate.tsx      # Password protection
│   │   ├── config/
│   │   │   └── traffic-sources.ts        # Traffic data source config
│   │   ├── hooks/
│   │   │   └── useStores.ts              # React Query hooks
│   │   ├── services/
│   │   │   ├── api.ts                    # Axios API client
│   │   │   ├── arcgis-traffic.ts         # ArcGIS traffic layer
│   │   │   └── mapbox-isochrone.ts       # Isochrone service
│   │   ├── store/
│   │   │   └── useMapStore.ts            # Zustand state management
│   │   ├── types/
│   │   │   └── store.ts                  # TypeScript interfaces
│   │   └── utils/
│   │       ├── building-layer-styles.ts
│   │       ├── listingLinks.ts
│   │       ├── mapbox-expressions.ts
│   │       └── poi-layer-styles.ts
│   ├── package.json
│   ├── nginx.conf
│   ├── entrypoint.sh
│   ├── Dockerfile                        # Development
│   └── Dockerfile.prod                   # Production (nginx)
├── scripts/
│   ├── download_national_boundaries.py   # Per-state GeoJSON download
│   ├── merge_national_boundaries.py      # Merge into national files
│   ├── upload_national_tilesets.sh       # Upload to Mapbox Tilesets API
│   ├── add_population_to_tilesets.py
│   ├── download-iowa-traffic.js
│   └── download-traffic-data.js
├── mapbox-tilesets/                      # GeoJSON/NDJSON for Mapbox uploads
├── data/                                 # Traffic count data
├── docker-compose.yml
├── CLAUDE.md
├── README.md
└── MAPBOX_TILESETS.md
```

---

## Data Architecture

### Competitor Data
| Brand | Records | Geocoded | DB Key |
|-------|---------|----------|--------|
| CSOKi (Cellular Sales) | 860 | 749 | `csoki` |
| Russell Cellular | 686 | 593 | `russell_cellular` |
| T-Mobile | 210 | 198 | `tmobile` |
| US Cellular | 85 | 79 | `uscellular` |
| Verizon Corporate | 40 | 38 | `verizon_corporate` |
| Victra | 37 | 31 | `victra` |
| **Total** | **1,918** | **1,688** | |

### Database Tables
- `stores` - Competitor locations with PostGIS geography column
- `team_properties` - Team-flagged property opportunities
- `scraped_listings` - Cached Crexi/LoopNet listings

### Boundary Tilesets (Mapbox)
Configured in `MapboxMap.tsx` via `BOUNDARY_TILESETS`:
- **Counties:** National county boundaries with POPULATION, MEDIAN_INCOME, POP_DENSITY
- **Cities:** City/place boundaries
- **ZCTAs:** ZIP Code Tabulation Areas
- **Census Tracts:** Tract-level boundaries

Tileset properties: `POPULATION`, `MEDIAN_INCOME`, `POP_DENSITY`, `NAME`, `GEOID`

Data pipeline: `download_national_boundaries.py` -> `merge_national_boundaries.py` -> `upload_national_tilesets.sh`

---

## API Endpoints

### Locations (`/api/v1/locations/`)
```
GET    /                              # List stores (brand, state, city, limit, offset)
GET    /brands/                       # Available brand names
GET    /stats/                        # Store count by brand with states
GET    /state/{state}/                # Stores in specific state
GET    /{store_id}/                   # Get specific store
POST   /within-bounds/                # Stores in map viewport
POST   /within-radius/                # Stores within radius of point
POST   /nearest-competitors/          # Nearest competitor of each brand
```

### Analysis (`/api/v1/analysis/`)
```
# Core Analysis
POST   /trade-area/                   # Google Places POI analysis
POST   /mapbox-trade-area/            # Mapbox Places POI analysis
POST   /demographics/                 # ArcGIS demographics (1/3/5 mi)
POST   /parcel/                       # ReportAll parcel lookup
POST   /property-search/              # Property search (legacy Tavily/AI)

# ATTOM Properties
POST   /properties/search/            # ATTOM property search by radius
POST   /properties/search-bounds/     # ATTOM property search by bounds

# Traffic
POST   /traffic-counts/               # StreetLight traffic analysis
POST   /traffic-counts/estimate/      # Estimate segment count

# Drive-Time Matrix
POST   /matrix/                       # Mapbox Matrix (distance/time)
POST   /matrix/batched/               # Batched matrix for large datasets
POST   /competitor-access/            # Drive-time to nearby competitors
GET    /matrix/cache-stats/           # Matrix cache statistics
POST   /matrix/clear-cache/           # Clear matrix cache

# Isochrones
POST   /isochrone/                    # Single point isochrone
POST   /isochrone/multi/              # Multi-point isochrone

# Boundary Data
GET    /demographic-boundaries/        # Choropleth data (state, metric, geography)
GET    /boundaries/counties/           # County boundaries for state
GET    /boundaries/cities/             # City boundaries for state
GET    /boundaries/zipcodes/           # ZCTA boundaries for state

# Saved Analyses (Mapbox Datasets)
POST   /datasets/save/                # Save analysis
GET    /datasets/                     # List saved analyses
GET    /datasets/{id}/                # Get saved analysis
GET    /datasets/{id}/features/       # Get analysis features
DELETE /datasets/{id}/                # Delete saved analysis
GET    /datasets/mapbox/              # List Mapbox datasets

# Utilities
GET    /check-keys/                   # Check all API key status
POST   /regeocode-stores/             # Re-geocode stores
GET    /regeocode-status/             # Check geocoding status
GET    /validate-store-coords/        # Validate store coordinates
```

### Opportunities (`/api/v1/opportunities/`)
```
POST   /search                        # CSOKi-filtered opportunity search
GET    /stats                         # Opportunity signal metadata
```

### Listings (`/api/v1/listings/`)
```
POST   /scrape                        # Trigger listing scrape
GET    /scrape/{job_id}               # Scrape job status
GET    /search                        # Search cached listings
POST   /search-bounds                 # Search listings in bounds
GET    /sources                       # Listing source status
GET    /diagnostics                   # Crexi/Playwright diagnostics
DELETE /{listing_id}                  # Deactivate listing
POST   /import-url                    # Import from URL
POST   /import-urls-batch             # Batch import from URLs
POST   /fetch-crexi-area              # Fetch Crexi listings for area
```

### Team Properties (`/api/v1/team-properties/`)
```
POST   /                              # Create team property flag
GET    /                              # List team properties
GET    /{id}                          # Get specific property
PUT    /{id}                          # Update team property
DELETE /{id}                          # Delete team property
POST   /in-bounds/                    # Properties in map bounds
```

### Traffic (`/api/v1/traffic/`)
```
GET    /states/                       # Available traffic data states
GET    /{state_code}/                 # Traffic data for state
DELETE /cache/{state_code}/           # Clear traffic cache
```

---

## CSOKi Opportunities Layer

The Opportunities layer is the core Phase 3 feature. It uses ATTOM property data filtered by CSOKi-specific criteria:

### Filter Criteria
- **Parcel size:** 0.8-2 acres
- **Building size:** 2,500-6,000 sqft (if building exists)
- **Property types:** Retail (preferred), Office (acceptable), Land (empty parcels)
- **Exclude:** Multi-tenant buildings, shopping centers, strip malls
- **Proximity:** Must be within 1 mile of a Verizon-family store (Russell Cellular, Victra, Verizon Corporate)

### Opportunity Ranking (Priority Order)
| Rank | Signal | Points |
|------|--------|--------|
| 1 | Empty parcels (land only) | 100 |
| 2 | Vacant properties | 80 |
| 3 | Out-of-state/absentee owners | 60 |
| 4 | Tax liens/pressure | 50 |
| 5 | Aging owners (estate/trust) | 40 |
| 6 | Small single-tenant buildings | 30 |
| Bonus | Foreclosure/distress | 70 |

### Verizon-Family Brands
```python
VERIZON_FAMILY_BRANDS = ["russell_cellular", "victra", "verizon_corporate"]
```

---

## Environment Variables

### Backend (Railway)
```env
DATABASE_URL=postgresql://...              # Railway PostgreSQL (auto-provided)

# Active API Keys
GOOGLE_PLACES_API_KEY=...                  # POI search (trade area analysis)
ARCGIS_API_KEY=...                         # Demographics (GeoEnrichment)
MAPBOX_ACCESS_TOKEN=...                    # Mapbox services (isochrone, matrix, places, datasets)
ATTOM_API_KEY=...                          # Property intelligence & opportunity signals
REPORTALL_API_KEY=...                      # Parcel details, ownership, zoning
STREETLIGHT_API_KEY=...                    # Traffic count data
TAVILY_API_KEY=...                         # AI-powered property search (legacy)
CREXI_API_KEY=...                          # Crexi listing access

# Listing Scraper Credentials
CREXI_USERNAME=... (or CREXI_EMAIL=...)    # Crexi login
CREXI_PASSWORD=...                         # Crexi password
```

### Frontend (Railway)
```env
VITE_API_URL=https://backend-production-cf26.up.railway.app
VITE_MAPBOX_TOKEN=...                      # Mapbox GL JS map rendering
```

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Map Library | Mapbox GL JS | Vector tiles, custom layers, tilesets, isochrones, matrix API |
| POI Data | Google Places + Mapbox Places | Dual-source for comprehensive coverage |
| Demographics | ArcGIS GeoEnrichment | Comprehensive US demographic data |
| Property Data | ATTOM API | Reliable commercial property intelligence |
| Parcel Data | ReportAll API | Precise boundaries, ownership, zoning |
| Traffic Data | StreetLight API | Industry-standard traffic analytics |
| Boundary Overlays | Mapbox Vector Tilesets | Performant rendering of county/city/ZCTA/tract polygons |
| Listing Data | Crexi (browser automation) | Primary CRE listing source |
| State Management | Zustand | Simple, lightweight, React-friendly |
| Hosting | Railway | Easy deployment, PostgreSQL + PostGIS support |
| PDF Export | jsPDF | Client-side generation, no server load |

---

## Deployment

### Railway Services
- **backend**: FastAPI app with PostGIS connection
- **frontend**: React app served via nginx (Dockerfile.prod)
- **PostgreSQL**: Railway-managed with PostGIS extension

### Deploy
```bash
git push origin main    # Auto-deploys on push
```

---

## Notes for Development

### Important Implementation Details

1. **API URL trailing slashes**: FastAPI routes defined with trailing slashes; frontend API calls match.

2. **HTTPS Middleware**: Backend uses custom middleware to handle X-Forwarded-Proto from Railway proxy.

3. **CORS Configuration** in `backend/app/core/config.py`:
   - `https://dashboard.fivecodevelopment.com`
   - `https://frontend-production-12b6.up.railway.app`
   - `http://localhost:5173` (dev)
   - `http://localhost:3000` (dev)

4. **Database Auto-Seeding**: On startup, `main.py` imports all CSVs from `/data/competitors/` if database is empty.

5. **Map Navigation**: Uses Mapbox GL JS with `react-map-gl`. Map state managed through Zustand store (`useMapStore.ts`).

6. **Boundary Tilesets**: County/city/ZCTA/tract boundaries use Mapbox vector tilesets (NOT dynamic GeoJSON). Tileset IDs and source-layer names configured in `BOUNDARY_TILESETS` in `MapboxMap.tsx` (~line 88). Source-layer names are set during upload and must be verified in Mapbox Studio.

7. **Demographic Choropleth**: `demographicMetric` state controls county fill color. Values: `'population' | 'income' | 'density'`.

8. **Census Tracts**: Need pagination (500 per batch) - states like CA/TX have thousands. Tracts use NDJSON format for large-file compatibility with Mapbox Tilesets Service.

9. **ZCTAs**: Population fetched once nationally (single Census ACS request), not per-state. Need deduplication by GEOID20 since bounding box queries create overlap at borders.

10. **Shared Haversine**: Single implementation in `backend/app/utils/geo.py` (returns miles). Note: `mapbox_places.py` has its own haversine that returns meters with lat-first parameter order.

### Brand Colors
```typescript
BRAND_COLORS = {
  csoki: '#E31837',           // Red
  russell_cellular: '#FF6B00', // Orange
  verizon_corporate: '#CD040B', // Verizon Red
  victra: '#000000',           // Black
  tmobile: '#E20074',          // Magenta
  uscellular: '#00A3E0',       // Blue
}
```

### Opportunity Signal Types
- `tax_delinquent` - Delinquent taxes (HIGH)
- `tax_pressure` - Recent tax increases (MEDIUM)
- `distress` - Foreclosure/pre-foreclosure (HIGH)
- `vacant_property` - Currently unoccupied (HIGH)
- `absentee_owner` - Out-of-state owner (MEDIUM)
- `long_term_owner` - Same owner 15+ years (MEDIUM)
- `estate_ownership` - Trust or estate (MEDIUM)
- `undervalued` - Assessed below market (MEDIUM)
