# CSOKi Site Selection Platform

An AI-powered site selection dashboard for Cellular Sales to identify optimal locations for new retail stores.

## Target Markets
- **Primary:** Iowa & Nebraska
- **Secondary:** Nevada & Idaho

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Mapbox API token (get one at [mapbox.com](https://account.mapbox.com/))

### Setup

1. **Clone and configure environment:**
   ```bash
   cd csoki-site-selection

   # Backend environment
   cp backend/.env.example backend/.env
   # Edit backend/.env and add your API keys

   # Frontend environment
   cp frontend/.env.example frontend/.env
   # Edit frontend/.env and add your Mapbox token
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Import competitor data:**
   ```bash
   docker-compose exec backend python scripts/import_data.py
   ```

4. **Access the application:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Development

### Backend Only
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Only
```bash
cd frontend
npm install
npm run dev
```

## Data Sources

| Brand | Records | Status |
|-------|---------|--------|
| CSOKi (Cellular Sales) | 860 | ✅ Complete |
| Russell Cellular | 686 | ✅ Complete |
| Verizon Corporate | 40 | ✅ Complete |
| Victra | 37 | ✅ Complete |
| T-Mobile | 210 | ✅ Complete |
| US Cellular | 85 | ✅ Complete |

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostGIS
- **Frontend:** React 18, TypeScript, Mapbox GL JS, TailwindCSS
- **Database:** PostgreSQL 15 with PostGIS
- **Cache:** Redis (for future phases)

## Project Structure

```
csoki-site-selection/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # API endpoints
│   │   ├── core/            # Config, database
│   │   ├── models/          # SQLAlchemy models
│   │   └── services/        # Business logic
│   ├── data/competitors/    # Store location CSVs
│   └── scripts/             # Data import scripts
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── services/        # API client
│   │   ├── store/           # Zustand state
│   │   └── types/           # TypeScript types
│   └── package.json
└── docker-compose.yml
```

## API Endpoints

- `GET /api/v1/locations` - List all stores with filtering
- `GET /api/v1/locations/brands` - Get available brands
- `GET /api/v1/locations/stats` - Store count by brand
- `POST /api/v1/locations/within-bounds` - Stores in map bounds
- `POST /api/v1/locations/within-radius` - Stores within radius

## Development Phases

- [x] **Phase 1:** Project scaffolding, data import, basic map
- [ ] **Phase 2:** Demographics integration, advanced filtering
- [ ] **Phase 3:** Analysis tools, drive-time radius
- [ ] **Phase 4:** AI assistant integration
- [ ] **Phase 5:** Reports and export features
