# Boundary Layer Options for CSOKi Platform
## February 5, 2026

**Question:** Can we add Mapbox Boundaries as a toggle, and can we use ArcGIS data for custom boundaries?

**Answer:** Yes to both! Here are your options:

---

## Option 1: Mapbox Boundaries (Easiest - Plug & Play)

### What It Is
Mapbox provides a **pre-built boundaries tileset** (`mapbox.boundaries-adm-v4`) with:
- Countries, states, counties, cities
- Postal codes (ZIP codes)
- Neighborhoods (in major cities)
- Already optimized vector tiles (fast rendering)

### Implementation Complexity
⭐ **1/5** - Literally 10 lines of code to add

### Cost
**$0** - Included with your Mapbox plan

### Code Example (Add to MapboxMap.tsx)
```typescript
// In MapboxMap.tsx, add this source and layer:

{visibleLayersArray.includes('boundaries') && (
  <>
    <Source
      id="mapbox-boundaries"
      type="vector"
      url="mapbox://mapbox.boundaries-adm-v4"
    >
      {/* County boundaries */}
      <Layer
        id="county-boundaries"
        type="line"
        source-layer="boundaries_admin_2"  // Admin level 2 = counties
        paint={{
          'line-color': '#627BC1',
          'line-width': 2,
          'line-opacity': 0.8,
        }}
      />
      
      {/* City boundaries */}
      <Layer
        id="city-boundaries"
        type="line"
        source-layer="boundaries_admin_3"  // Admin level 3 = cities
        paint={{
          'line-color': '#4CAF50',
          'line-width': 1.5,
          'line-opacity': 0.6,
        }}
      />
      
      {/* Postal codes (optional) */}
      <Layer
        id="postal-boundaries"
        type="line"
        source-layer="boundaries_postal_code"
        minzoom={10}  // Only show when zoomed in
        paint={{
          'line-color': '#FF9800',
          'line-width': 1,
          'line-dasharray': [2, 2],
          'line-opacity': 0.5,
        }}
      />
    </Source>
  </>
)}
```

### Add to MapLayers.tsx Sidebar
```typescript
boundaries: {
  id: 'boundaries',
  name: 'Administrative Boundaries',
  icon: Map,  // or Grid icon
  color: '#627BC1',
  description: 'Counties, cities, ZIP codes',
},
```

**Time to implement:** 15-20 minutes  
**Testing:** Toggle on/off, zoom to different levels

---

## Option 2: ArcGIS Boundaries (More Flexible - Custom Data)

### What It Is
Use your **existing ArcGIS API key** to fetch:
- Census boundaries (tracts, block groups)
- Custom geographic areas
- Administrative boundaries
- Any ArcGIS Living Atlas dataset

### Implementation Complexity
⭐⭐⭐ **3/5** - Requires backend proxy + frontend layer

### Cost
- **ArcGIS API:** Already configured (check your usage tier)
- **Mapbox:** $0 (just rendering)

### Architecture
```
Frontend → Backend API → ArcGIS REST API → Return GeoJSON → Display on map
```

### Backend Implementation (New Service)

**File:** `backend/app/services/arcgis_boundaries.py`

```python
"""
ArcGIS Boundaries Service - Fetch census and administrative boundaries
"""
import httpx
from typing import Optional, List, Dict, Any
from app.core.config import settings

async def fetch_county_boundaries(state: str) -> Dict[str, Any]:
    """
    Fetch county boundaries from ArcGIS Living Atlas.
    
    Uses: https://services.arcgis.com/.../USA_Counties/FeatureServer/0
    """
    if not settings.ARCGIS_API_KEY:
        raise ValueError("ArcGIS API key not configured")
    
    url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Counties_Generalized_Boundaries/FeatureServer/0/query"
    
    params = {
        "where": f"STATE_ABBR = '{state}'",
        "outFields": "NAME,STATE_ABBR,FIPS",
        "f": "geojson",
        "token": settings.ARCGIS_API_KEY,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_census_tracts(
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
) -> Dict[str, Any]:
    """
    Fetch census tract boundaries within map bounds.
    
    Uses: ArcGIS Census Boundaries service
    """
    if not settings.ARCGIS_API_KEY:
        raise ValueError("ArcGIS API key not configured")
    
    # Build geometry envelope
    geometry = {
        "xmin": min_lng,
        "ymin": min_lat,
        "xmax": max_lng,
        "ymax": max_lat,
        "spatialReference": {"wkid": 4326}
    }
    
    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/8/query"
    
    params = {
        "geometry": str(geometry),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "GEOID,NAME,ALAND,AWATER",
        "f": "geojson",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_zip_code_boundaries(state: str) -> Dict[str, Any]:
    """
    Fetch ZIP code boundaries for a state.
    """
    if not settings.ARCGIS_API_KEY:
        raise ValueError("ArcGIS API key not configured")
    
    url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_ZIP_Code_Areas/FeatureServer/0/query"
    
    params = {
        "where": f"STATE = '{state}'",
        "outFields": "ZIP_CODE,PO_NAME,STATE,POPULATION",
        "f": "geojson",
        "token": settings.ARCGIS_API_KEY,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
```

### Backend API Endpoint

**File:** `backend/app/api/routes/boundaries.py`

```python
"""
Boundaries API - Fetch administrative and census boundaries
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.services.arcgis_boundaries import (
    fetch_county_boundaries,
    fetch_census_tracts,
    fetch_zip_code_boundaries,
)

router = APIRouter(prefix="/boundaries", tags=["boundaries"])


@router.get("/counties/{state}")
async def get_county_boundaries(state: str):
    """Get county boundaries for a state."""
    try:
        data = await fetch_county_boundaries(state)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/census-tracts")
async def get_census_tracts(
    min_lat: float = Query(...),
    max_lat: float = Query(...),
    min_lng: float = Query(...),
    max_lng: float = Query(...),
):
    """Get census tract boundaries within map viewport."""
    try:
        data = await fetch_census_tracts(min_lat, max_lat, min_lng, max_lng)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zip-codes/{state}")
async def get_zip_code_boundaries(state: str):
    """Get ZIP code boundaries for a state."""
    try:
        data = await fetch_zip_code_boundaries(state)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Frontend Implementation

**File:** `frontend/src/services/api.ts`

```typescript
export const boundariesApi = {
  // Get county boundaries
  getCountyBoundaries: async (state: string): Promise<any> => {
    const { data } = await api.get(`/boundaries/counties/${state}`);
    return data;
  },

  // Get census tracts
  getCensusTracts: async (bounds: {
    min_lat: number;
    max_lat: number;
    min_lng: number;
    max_lng: number;
  }): Promise<any> => {
    const { data } = await api.get('/boundaries/census-tracts', { params: bounds });
    return data;
  },

  // Get ZIP codes
  getZipCodes: async (state: string): Promise<any> => {
    const { data } = await api.get(`/boundaries/zip-codes/${state}`);
    return data;
  },
};
```

**In MapboxMap.tsx:**

```typescript
// State for boundaries
const [boundariesData, setBoundariesData] = useState<any>(null);
const [isLoadingBoundaries, setIsLoadingBoundaries] = useState(false);

// Fetch boundaries when toggle is enabled
useEffect(() => {
  const showBoundaries = visibleLayersArray.includes('arcgis_boundaries');

  if (showBoundaries && mapBounds) {
    const fetchBoundaries = async () => {
      setIsLoadingBoundaries(true);
      try {
        // Fetch census tracts within current viewport
        const result = await boundariesApi.getCensusTracts({
          min_lat: mapBounds.south,
          max_lat: mapBounds.north,
          min_lng: mapBounds.west,
          max_lng: mapBounds.east,
        });
        setBoundariesData(result);
      } catch (error) {
        console.error('[Boundaries] Error fetching:', error);
        setBoundariesData(null);
      } finally {
        setIsLoadingBoundaries(false);
      }
    };

    fetchBoundaries();
  } else if (!showBoundaries) {
    setBoundariesData(null);
  }
}, [visibleLayersArray, mapBounds]);

// Render boundaries as a layer
{boundariesData && (
  <Source
    id="arcgis-boundaries"
    type="geojson"
    data={boundariesData}
  >
    <Layer
      id="census-tracts-fill"
      type="fill"
      paint={{
        'fill-color': '#627BC1',
        'fill-opacity': 0.1,
      }}
    />
    <Layer
      id="census-tracts-line"
      type="line"
      paint={{
        'line-color': '#627BC1',
        'line-width': 1.5,
        'line-opacity': 0.6,
      }}
    />
  </Source>
)}
```

**Time to implement:** 2-3 hours  
**Benefits:** 
- Use existing ArcGIS key
- Access to Census data
- Custom boundary filtering

---

## Option 3: Hybrid Approach (Recommended)

**Use both:**
- **Mapbox Boundaries** for basic/quick boundaries (counties, ZIP codes)
- **ArcGIS** for detailed Census data (tracts, block groups, demographics)

### Why Hybrid?
- Mapbox = Fast, free, zero backend work
- ArcGIS = Detailed census data you already pay for
- Toggle between them based on zoom level or user selection

### Implementation
```typescript
// Sidebar toggles:
boundaries: {
  id: 'boundaries',
  name: 'Administrative Boundaries',
  icon: Map,
  color: '#627BC1',
  description: 'Counties, cities, ZIP codes (Mapbox)',
},
census_boundaries: {
  id: 'census_boundaries',
  name: 'Census Boundaries',
  icon: BarChart,
  color: '#4CAF50',
  description: 'Census tracts, block groups (ArcGIS)',
},
```

---

## Recommendation

**Start with Option 1 (Mapbox Boundaries):**
- Easiest to implement (15 min)
- Free
- Works immediately
- Great for most use cases

**Then add Option 2 (ArcGIS) if you need:**
- Census tract boundaries
- Demographic overlays
- Custom geographic analysis
- Integration with your existing ArcGIS data

---

## Quick Win Code (Add Today - 15 Minutes)

**1. Add to `frontend/src/components/Sidebar/MapLayers.tsx`:**

```typescript
boundaries: {
  id: 'boundaries',
  name: 'Boundaries',
  icon: Grid,  // or Map icon
  color: '#627BC1',
  description: 'Administrative boundaries',
},
```

**2. Add to `frontend/src/components/Map/MapboxMap.tsx`:**

```typescript
{/* Administrative Boundaries */}
{visibleLayersArray.includes('boundaries') && (
  <Source
    id="mapbox-boundaries"
    type="vector"
    url="mapbox://mapbox.boundaries-adm-v4"
  >
    {/* Counties - only show at certain zoom levels */}
    <Layer
      id="county-boundaries"
      type="line"
      source-layer="boundaries_admin_2"
      minzoom={6}
      paint={{
        'line-color': '#627BC1',
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          6, 1,
          10, 2,
        ],
        'line-opacity': 0.8,
      }}
    />
  </Source>
)}
```

**3. Test it:**
- Toggle "Boundaries" in sidebar
- County lines should appear
- Adjust zoom to see line width changes

---

## Next Steps

1. **Immediate:** Add Mapbox Boundaries (Option 1) - 15 min
2. **This week:** Add ArcGIS Census boundaries if needed (Option 2) - 2-3 hours
3. **Future:** Add demographic overlays linked to boundaries (population density, income, etc.)

---

**Want me to implement Option 1 (Mapbox Boundaries) right now?** It's literally 3 file edits and will work immediately.
