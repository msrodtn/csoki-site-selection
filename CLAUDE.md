# CSOKi Site Selection Platform

## Project Overview

An AI-powered site selection dashboard for Cellular Sales (CSOKi) to identify optimal locations for new retail stores. The platform serves executive leadership with strategic market analysis, competitor mapping, and data-driven location recommendations.

### Target Markets
- **Primary:** Iowa & Nebraska
- **Secondary:** Nevada & Idaho

### Core Value Proposition
Enable data-driven expansion decisions by visualizing competitor landscapes, demographic opportunities, and market gaps across target regions.

---

## Technical Architecture

### Stack
- **Backend:** Python 3.11+ with FastAPI
- **Frontend:** React 18+ with TypeScript
- **Database:** PostgreSQL 15+ with PostGIS extension (geospatial)
- **Maps:** Mapbox GL JS or Deck.gl for interactive visualization
- **AI/ML:** OpenAI API for conversational features, scikit-learn for scoring models
- **Cache:** Redis for API response caching
- **Task Queue:** Celery for background data processing

### Project Structure
```
csoki-site-selection/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── locations.py
│   │   │   │   ├── analysis.py
│   │   │   │   ├── chat.py
│   │   │   │   └── reports.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── database.py
│   │   ├── models/
│   │   │   ├── store.py
│   │   │   ├── competitor.py
│   │   │   ├── market.py
│   │   │   └── analysis.py
│   │   ├── services/
│   │   │   ├── scoring.py
│   │   │   ├── demographics.py
│   │   │   ├── traffic.py
│   │   │   ├── geocoding.py
│   │   │   └── ai_assistant.py
│   │   └── main.py
│   ├── data/
│   │   ├── competitors/
│   │   │   ├── csoki_stores.csv
│   │   │   ├── russell_cellular_stores.csv
│   │   │   ├── verizon_corporate.csv
│   │   │   ├── victra_stores.csv
│   │   │   ├── tmobile_stores.csv
│   │   │   └── uscellular_stores.csv
│   │   └── reference/
│   │       ├── zip_demographics.csv
│   │       └── market_definitions.json
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   ├── Dashboard/
│   │   │   ├── Analysis/
│   │   │   ├── Chat/
│   │   │   └── Reports/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── store/
│   │   ├── types/
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── CLAUDE.md
└── README.md
```

---

## Data Architecture

### Competitor Data (Collected)
| Source | Records | Status |
|--------|---------|--------|
| CSOKi (Cellular Sales) | 860 | ✅ Complete |
| Russell Cellular | 686 | ✅ Complete |
| Verizon Corporate | TBD | ❌ Pending |
| Victra | TBD | ❌ Pending |
| T-Mobile | TBD | ❌ Pending |
| US Cellular | TBD | ❌ Pending |

### Store Data Schema
```sql
CREATE TABLE competitors (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(50) NOT NULL,
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    postal_code VARCHAR(10),
    location GEOGRAPHY(POINT, 4326),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_competitors_location ON competitors USING GIST(location);
CREATE INDEX idx_competitors_brand ON competitors(brand);
CREATE INDEX idx_competitors_state ON competitors(state);
```

### External Data Sources to Integrate
1. **Demographics:** US Census API (population, income, age, education)
2. **Traffic Data:** SafeGraph or similar foot traffic provider
3. **Points of Interest:** OpenStreetMap / Overpass API
4. **Economic Indicators:** BLS, BEA APIs
5. **Retail Trends:** Consider Placer.ai or similar

---

## Core Features

### 1. Interactive Map Dashboard
- Multi-layer competitor visualization (toggle by brand)
- Heat maps showing competition density
- Draw custom analysis areas (polygon/radius)
- Drive-time isochrones (5/10/15 minute)
- Demographic overlay layers

### 2. AI Location Scoring
Weighted algorithm considering:
- **Competition Factor (30%):** Distance to nearest competitors, competitor density
- **Demographics (25%):** Population density, median income, age distribution
- **Traffic (20%):** Foot traffic, vehicle counts, retail activity
- **Accessibility (15%):** Major road proximity, visibility, parking
- **Market Gaps (10%):** Underserved areas relative to population

### 3. Conversational AI Assistant
Natural language queries like:
- "Show me the best opportunities in Des Moines"
- "Where are Russell Cellular stores without nearby CSOKi presence?"
- "Compare demographics of Omaha vs Lincoln markets"
- "What's the competition density within 5 miles of [address]?"

### 4. Predictive Analytics
- Estimate potential revenue based on comparable locations
- Cannibalization risk assessment for new locations
- Market saturation analysis

### 5. Reporting & Export
- Executive summary PDFs
- Custom area reports
- Data export (CSV, GeoJSON)
- Saved analysis workflows

---

## Development Phases

### Phase 1: Foundation (Weeks 1-2)
- [ ] Project scaffolding (backend + frontend)
- [ ] Database setup with PostGIS
- [ ] Import existing competitor data (CSOKi, Russell Cellular)
- [ ] Basic map visualization with competitor pins
- [ ] Geocode all addresses to lat/lng

### Phase 2: Data Enrichment (Weeks 3-4)
- [ ] Scrape remaining competitors (Verizon, Victra, T-Mobile, US Cellular)
- [ ] Census API integration for demographics
- [ ] Basic demographic overlay on map
- [ ] Filter/search functionality

### Phase 3: Analysis Tools (Weeks 5-6)
- [ ] Location scoring algorithm
- [ ] Draw-to-analyze tool (custom polygons)
- [ ] Drive-time radius analysis
- [ ] Competition density heat maps

### Phase 4: AI Integration (Weeks 7-8)
- [ ] Conversational assistant (OpenAI integration)
- [ ] Natural language to map query translation
- [ ] AI-generated location recommendations
- [ ] Insight summarization

### Phase 5: Polish & Reports (Weeks 9-10)
- [ ] Executive dashboard view
- [ ] PDF report generation
- [ ] Saved analyses / bookmarks
- [ ] Performance optimization
- [ ] User documentation

---

## API Endpoints

### Locations
```
GET    /api/v1/locations                    # List all competitor locations
GET    /api/v1/locations/{id}               # Get single location
GET    /api/v1/locations/brand/{brand}      # Filter by brand
GET    /api/v1/locations/state/{state}      # Filter by state
POST   /api/v1/locations/within-bounds      # Locations within map bounds
POST   /api/v1/locations/within-radius      # Locations within radius of point
```

### Analysis
```
POST   /api/v1/analysis/score-location      # Score a potential location
POST   /api/v1/analysis/competition-density # Get density for area
POST   /api/v1/analysis/demographics        # Demographics for area
POST   /api/v1/analysis/drive-time          # Generate isochrone
GET    /api/v1/analysis/market-gaps         # Identify underserved areas
```

### AI Assistant
```
POST   /api/v1/chat/message                 # Send message to AI
GET    /api/v1/chat/history                 # Get conversation history
POST   /api/v1/chat/execute-action          # Execute AI-suggested action
```

### Reports
```
POST   /api/v1/reports/generate             # Generate PDF report
GET    /api/v1/reports/{id}                 # Download report
GET    /api/v1/reports/templates            # List report templates
```

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/csoki_sites
REDIS_URL=redis://localhost:6379

# APIs
OPENAI_API_KEY=sk-...
MAPBOX_ACCESS_TOKEN=pk-...
CENSUS_API_KEY=...

# App
SECRET_KEY=...
DEBUG=true
CORS_ORIGINS=http://localhost:3000
```

---

## Coding Standards

### Python (Backend)
- Use type hints throughout
- Pydantic models for request/response validation
- Async endpoints where beneficial
- SQLAlchemy 2.0 style queries
- pytest for testing

### TypeScript (Frontend)
- Strict mode enabled
- Functional components with hooks
- Zustand or Redux Toolkit for state
- React Query for API calls
- Tailwind CSS for styling

### Git Workflow
- `main` - production-ready code
- `develop` - integration branch
- `feature/*` - new features
- `fix/*` - bug fixes
- Conventional commits (feat:, fix:, docs:, etc.)

---

## Key Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Map Library | Mapbox GL JS | Best balance of features, performance, and React integration |
| AI Provider | OpenAI | GPT-4 for conversational quality, function calling for actions |
| Geospatial DB | PostGIS | Industry standard, powerful spatial queries |
| Auth (future) | Auth0 or Clerk | When multi-user needed, easy integration |

---

## Commands Reference

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Database
docker-compose up -d postgres redis
alembic upgrade head

# Full stack
docker-compose up --build
```

---

## Notes for Claude

When working on this project:

1. **Geospatial queries** should use PostGIS functions (ST_Distance, ST_DWithin, ST_Contains)
2. **Map interactions** should debounce API calls to avoid excessive requests
3. **Scoring algorithm** weights are configurable - store in database for easy tuning
4. **AI responses** should include actionable map commands (zoom to, highlight, filter)
5. **Data freshness** - competitor data should be refreshable; design for periodic updates
6. **Performance** - Consider caching demographic data by zip code

### Current Data Files
- `/data/competitors/csoki_stores.csv` - 860 CSOKi locations (street, city, state, zip)
- `/data/competitors/russell_cellular_stores.csv` - 686 Russell Cellular locations

### Pending Data Collection
- Verizon Corporate stores (scrape from verizon.com/stores)
- Victra stores (scrape from victra.com/stores)
- T-Mobile stores (scrape from t-mobile.com/store-locator)
- US Cellular stores (scrape from uscellular.com/stores)
