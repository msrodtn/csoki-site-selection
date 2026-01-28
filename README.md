# CSOKi Site Selection Platform

An AI-powered site selection dashboard for Cellular Sales to identify optimal locations for new retail stores.

## Live Production

- **Dashboard:** https://dashboard.fivecodevelopment.com
- **API:** https://backend-production-cf26.up.railway.app
- **Password:** `!FiveCo`

## Target Markets
- **Primary:** Iowa & Nebraska
- **Secondary:** Nevada & Idaho

## Current Features (Phase 1 Complete)

- Interactive Google Maps with 1,688 geocoded store locations
- 6 competitor brand toggles (CSOKi, Russell Cellular, T-Mobile, US Cellular, Verizon, Victra)
- Market/state selection (Iowa, Nebraska, Nevada, Idaho)
- Store info popups on marker click
- Password-protected access
- Deployed on Railway with custom domain

## Data Sources

| Brand | Records | Geocoded | Status |
|-------|---------|----------|--------|
| CSOKi (Cellular Sales) | 860 | 749 | ✅ Complete |
| Russell Cellular | 686 | 593 | ✅ Complete |
| T-Mobile | 210 | 198 | ✅ Complete |
| US Cellular | 85 | 79 | ✅ Complete |
| Verizon Corporate | 40 | 38 | ✅ Complete |
| Victra | 37 | 31 | ✅ Complete |
| **Total** | **1,918** | **1,688** | **88% geocoded** |

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostGIS
- **Frontend:** React 18, TypeScript, Google Maps API, TailwindCSS, Zustand
- **Database:** PostgreSQL 15 with PostGIS (Railway)
- **Hosting:** Railway (backend + frontend + database)
- **Domain:** GoDaddy DNS → Railway

## Local Development

### Prerequisites
- Docker & Docker Compose
- Google Maps API key

### Setup

1. **Clone and configure environment:**
   ```bash
   cd csoki-site-selection

   # Backend environment
   cp backend/.env.example backend/.env

   # Frontend environment
   cp frontend/.env.example frontend/.env
   # Add your Google Maps API key to VITE_GOOGLE_MAPS_API_KEY
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Access the application:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Manual Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Deployment (Railway)

Both services auto-deploy from GitHub pushes. To manually deploy:

```bash
# Backend
cd backend && railway service backend && railway up

# Frontend
cd frontend && railway service frontend && railway up
```

## Project Structure

```
csoki-site-selection/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # API endpoints
│   │   ├── core/            # Config, database, CORS
│   │   ├── models/          # SQLAlchemy models
│   │   └── services/        # Data import, geocoding
│   ├── data/competitors/    # Store location CSVs (pre-geocoded)
│   ├── scripts/             # Batch geocoding script
│   ├── Dockerfile.prod      # Production Dockerfile
│   └── railway.toml         # Railway config
├── frontend/
│   ├── src/
│   │   ├── components/      # React components (Map, Sidebar, Auth)
│   │   ├── hooks/           # React Query hooks
│   │   ├── services/        # API client (axios)
│   │   ├── store/           # Zustand state management
│   │   └── types/           # TypeScript types
│   ├── Dockerfile.prod      # Production Dockerfile (nginx)
│   ├── nginx.conf           # Nginx config for SPA
│   └── railway.toml         # Railway config
└── docker-compose.yml
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/locations/` | GET | List stores with filtering (brand, state, city) |
| `/api/v1/locations/brands/` | GET | Get available brand names |
| `/api/v1/locations/stats/` | GET | Store count by brand with states |
| `/api/v1/locations/state/{state}/` | GET | Stores in a specific state |
| `/api/v1/locations/within-bounds/` | POST | Stores within map viewport |
| `/api/v1/locations/within-radius/` | POST | Stores within radius of point |
| `/health` | GET | Health check |

## Development Phases

- [x] **Phase 1:** Foundation - Project scaffolding, data import, geocoding, map visualization, deployment
- [ ] **Phase 2:** Data Enrichment - Census demographics, population overlays, zip code search
- [ ] **Phase 3:** Analysis Tools - Scoring algorithm, heat maps, drive-time isochrones
- [ ] **Phase 4:** AI Integration - Natural language queries, AI recommendations
- [ ] **Phase 5:** Reports - PDF generation, saved analyses, top 5-10 site recommendations

## Key Files Modified (Jan 28, 2026)

- `backend/app/main.py` - Added HTTPS redirect middleware for Railway
- `backend/app/core/config.py` - Added production CORS origins
- `frontend/src/services/api.ts` - API client with trailing slash URLs
- `frontend/src/components/Map/StoreMap.tsx` - Google Maps integration
- `frontend/src/components/Auth/PasswordGate.tsx` - Password protection
- `backend/scripts/batch_geocode.py` - US Census Bureau batch geocoder
