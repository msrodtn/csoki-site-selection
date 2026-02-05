# US Boundary Tileset Automation Guide

## Overview

This document provides a complete, automated approach to downloading Census TIGER boundaries and ArcGIS demographic data for **all 50 US states + DC**, then uploading them as Mapbox tilesets for use in the CSOKi Site Selection platform.

---

## Data Sources

### 1. Census TIGER Boundaries (Free, No API Key)
| Boundary Type | MapServer Layer | URL Pattern |
|---------------|-----------------|-------------|
| **Counties** | Layer 86 | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/86/query` |
| **Cities/Places** | Layer 24 | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/24/query` |
| **ZIP Codes (ZCTA)** | Layer 2 | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/2/query` |
| **Census Tracts** | Layer 8 | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/8/query` |

### 2. ArcGIS Living Atlas Demographics (Free, No API Key)
| Data Type | FeatureServer | Fields |
|-----------|---------------|--------|
| **Population** | `ACS_Total_Population_Boundaries` | `B01001_001E` (Total Pop), `Shape__Area` |
| **Income** | `ACS_Median_Income_by_Race_and_Age_Selp_Emp_Boundaries` | `B19049_001E` (Median HH Income) |

**Base URL:** `https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/`

**Layer Indices:**
- Layer 0 = State level
- Layer 1 = County level
- Layer 2 = Tract level

---

## State FIPS Codes (All 50 States + DC)

```javascript
const STATE_FIPS = {
  "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
  "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
  "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
  "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
  "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
  "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
  "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
  "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
  "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
  "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
  "WY": "56"
};
```

---

## Automated Download Script

### Prerequisites

```bash
# Install required tools
npm install -g @mapbox/mapbox-gl-js
pip install mapbox-tilesets
brew install jq  # or apt-get install jq

# Set environment variables
export MAPBOX_ACCESS_TOKEN="your_mapbox_token_here"
```

### Master Download Script: `download_all_boundaries.sh`

```bash
#!/bin/bash
# download_all_boundaries.sh
# Downloads Census TIGER boundaries for all US states

set -e

OUTPUT_DIR="./boundary_data"
mkdir -p "$OUTPUT_DIR/counties"
mkdir -p "$OUTPUT_DIR/cities"
mkdir -p "$OUTPUT_DIR/zctas"
mkdir -p "$OUTPUT_DIR/tracts"

# State FIPS codes
declare -A STATES=(
  ["AL"]="01" ["AK"]="02" ["AZ"]="04" ["AR"]="05" ["CA"]="06"
  ["CO"]="08" ["CT"]="09" ["DE"]="10" ["DC"]="11" ["FL"]="12"
  ["GA"]="13" ["HI"]="15" ["ID"]="16" ["IL"]="17" ["IN"]="18"
  ["IA"]="19" ["KS"]="20" ["KY"]="21" ["LA"]="22" ["ME"]="23"
  ["MD"]="24" ["MA"]="25" ["MI"]="26" ["MN"]="27" ["MS"]="28"
  ["MO"]="29" ["MT"]="30" ["NE"]="31" ["NV"]="32" ["NH"]="33"
  ["NJ"]="34" ["NM"]="35" ["NY"]="36" ["NC"]="37" ["ND"]="38"
  ["OH"]="39" ["OK"]="40" ["OR"]="41" ["PA"]="42" ["RI"]="44"
  ["SC"]="45" ["SD"]="46" ["TN"]="47" ["TX"]="48" ["UT"]="49"
  ["VT"]="50" ["VA"]="51" ["WA"]="53" ["WV"]="54" ["WI"]="55"
  ["WY"]="56"
)

TIGER_BASE="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer"

# Function to download with retry
download_with_retry() {
  local url="$1"
  local output="$2"
  local max_retries=3
  local retry=0

  while [ $retry -lt $max_retries ]; do
    echo "  Downloading: $output (attempt $((retry+1)))"
    if curl -s -f "$url" -o "$output"; then
      # Validate JSON
      if jq empty "$output" 2>/dev/null; then
        echo "  ✓ Success: $output"
        return 0
      fi
    fi
    retry=$((retry+1))
    sleep 2
  done
  echo "  ✗ Failed: $output"
  return 1
}

# Download Counties (Layer 86)
echo "=== Downloading Counties ==="
for state in "${!STATES[@]}"; do
  fips="${STATES[$state]}"
  url="${TIGER_BASE}/86/query?where=STATE%3D%27${fips}%27&outFields=NAME,BASENAME,GEOID,STATE,COUNTY,AREALAND&f=geojson&returnGeometry=true&outSR=4326"
  download_with_retry "$url" "$OUTPUT_DIR/counties/${state}_counties.geojson"
  sleep 0.5  # Rate limiting
done

# Download Cities/Places (Layer 24)
echo "=== Downloading Cities ==="
for state in "${!STATES[@]}"; do
  fips="${STATES[$state]}"
  url="${TIGER_BASE}/24/query?where=STATE%3D%27${fips}%27&outFields=NAME,BASENAME,GEOID,STATE,AREALAND,FUNCSTAT&f=geojson&returnGeometry=true&outSR=4326"
  download_with_retry "$url" "$OUTPUT_DIR/cities/${state}_cities.geojson"
  sleep 0.5
done

# Download Census Tracts (Layer 8)
echo "=== Downloading Census Tracts ==="
for state in "${!STATES[@]}"; do
  fips="${STATES[$state]}"
  url="${TIGER_BASE}/8/query?where=STATE%3D%27${fips}%27&outFields=NAME,GEOID,STATE,COUNTY,TRACT,AREALAND&f=geojson&returnGeometry=true&outSR=4326"
  download_with_retry "$url" "$OUTPUT_DIR/tracts/${state}_tracts.geojson"
  sleep 0.5
done

echo "=== Download Complete ==="
echo "Files saved to: $OUTPUT_DIR"
```

### ZIP Code Download Script: `download_zctas.sh`

ZIP codes (ZCTAs) don't have a STATE field, so we use bounding boxes:

```bash
#!/bin/bash
# download_zctas.sh
# Downloads ZCTA boundaries using state bounding boxes

set -e

OUTPUT_DIR="./boundary_data/zctas"
mkdir -p "$OUTPUT_DIR"

TIGER_ZCTA="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/2/query"

# State bounding boxes (minX, minY, maxX, maxY)
declare -A STATE_BOUNDS=(
  ["AL"]="-88.5,-30.2,-84.9,35.0"
  ["AK"]="-180.0,51.2,-129.0,71.4"
  ["AZ"]="-115.0,31.3,-109.0,37.0"
  ["AR"]="-94.6,33.0,-89.6,36.5"
  ["CA"]="-124.5,32.5,-114.1,42.0"
  ["CO"]="-109.1,36.9,-102.0,41.0"
  ["CT"]="-73.8,40.9,-71.8,42.1"
  ["DE"]="-75.8,38.4,-75.0,39.9"
  ["DC"]="-77.2,38.8,-76.9,39.0"
  ["FL"]="-87.7,24.4,-79.9,31.0"
  ["GA"]="-85.7,30.3,-80.8,35.0"
  ["HI"]="-160.3,18.9,-154.8,22.3"
  ["ID"]="-117.3,41.9,-111.0,49.1"
  ["IL"]="-91.6,36.9,-87.0,42.5"
  ["IN"]="-88.1,37.8,-84.8,41.8"
  ["IA"]="-96.7,40.3,-90.1,43.6"
  ["KS"]="-102.1,36.9,-94.6,40.0"
  ["KY"]="-89.6,36.5,-81.9,39.2"
  ["LA"]="-94.1,28.9,-88.8,33.0"
  ["ME"]="-71.1,42.9,-66.9,47.5"
  ["MD"]="-79.5,37.9,-75.0,39.8"
  ["MA"]="-73.5,41.2,-69.9,42.9"
  ["MI"]="-90.5,41.7,-82.1,48.3"
  ["MN"]="-97.3,43.5,-89.5,49.4"
  ["MS"]="-91.7,30.1,-88.1,35.0"
  ["MO"]="-95.8,35.9,-89.1,40.6"
  ["MT"]="-116.1,44.4,-104.0,49.0"
  ["NE"]="-104.1,39.9,-95.3,43.1"
  ["NV"]="-120.1,35.0,-114.0,42.1"
  ["NH"]="-72.6,42.7,-70.6,45.3"
  ["NJ"]="-75.6,38.9,-73.9,41.4"
  ["NM"]="-109.1,31.3,-103.0,37.0"
  ["NY"]="-79.8,40.5,-71.8,45.1"
  ["NC"]="-84.4,33.8,-75.4,36.6"
  ["ND"]="-104.1,45.9,-96.6,49.0"
  ["OH"]="-84.9,38.4,-80.5,42.0"
  ["OK"]="-103.1,33.6,-94.4,37.0"
  ["OR"]="-124.6,41.9,-116.5,46.3"
  ["PA"]="-80.6,39.7,-74.7,42.3"
  ["RI"]="-71.9,41.1,-71.1,42.0"
  ["SC"]="-83.4,32.0,-78.5,35.3"
  ["SD"]="-104.1,42.5,-96.4,46.0"
  ["TN"]="-90.4,34.9,-81.6,36.7"
  ["TX"]="-106.7,25.8,-93.5,36.5"
  ["UT"]="-114.1,37.0,-109.0,42.0"
  ["VT"]="-73.5,42.7,-71.5,45.0"
  ["VA"]="-83.7,36.5,-75.2,39.5"
  ["WA"]="-124.9,45.5,-116.9,49.0"
  ["WV"]="-82.7,37.2,-77.7,40.7"
  ["WI"]="-92.9,42.5,-86.2,47.1"
  ["WY"]="-111.1,40.9,-104.0,45.1"
)

for state in "${!STATE_BOUNDS[@]}"; do
  bounds="${STATE_BOUNDS[$state]}"
  IFS=',' read -r minX minY maxX maxY <<< "$bounds"

  echo "Downloading ZCTAs for $state..."
  url="${TIGER_ZCTA}?where=1%3D1&geometry=${minX},${minY},${maxX},${maxY}&geometryType=esriGeometryEnvelope&spatialRel=esriSpatialRelIntersects&outFields=NAME,GEOID,ZCTA5CE20,AREALAND&f=geojson&returnGeometry=true&outSR=4326"

  curl -s "$url" -o "$OUTPUT_DIR/${state}_zctas.geojson"

  # Validate
  if jq empty "$OUTPUT_DIR/${state}_zctas.geojson" 2>/dev/null; then
    echo "  ✓ $state ZCTAs downloaded"
  else
    echo "  ✗ $state ZCTAs failed"
  fi

  sleep 0.5
done

echo "=== ZCTA Download Complete ==="
```

---

## Merge and Upload to Mapbox

### Merge State Files into Regional Tilesets

```bash
#!/bin/bash
# merge_and_upload.sh
# Merges state GeoJSON files and uploads to Mapbox

set -e

INPUT_DIR="./boundary_data"
OUTPUT_DIR="./merged_tilesets"
mkdir -p "$OUTPUT_DIR"

# Define regions (customize as needed)
declare -A REGIONS=(
  ["midwest"]="IA NE MN WI IL IN MI OH"
  ["mountain"]="MT WY CO NV ID UT AZ NM"
  ["south"]="TX OK AR LA MS AL TN KY"
  ["northeast"]="NY PA NJ CT MA NH VT ME RI"
  ["southeast"]="FL GA SC NC VA WV MD DE DC"
  ["west"]="CA OR WA AK HI"
  ["plains"]="ND SD KS MO"
)

# Merge function using jq
merge_geojson() {
  local output_file="$1"
  shift
  local input_files=("$@")

  # Combine all features into one FeatureCollection
  jq -s '{ type: "FeatureCollection", features: [.[].features[]] | flatten }' "${input_files[@]}" > "$output_file"
}

# Merge Counties by Region
echo "=== Merging Counties ==="
for region in "${!REGIONS[@]}"; do
  states="${REGIONS[$region]}"
  files=()
  for state in $states; do
    if [ -f "$INPUT_DIR/counties/${state}_counties.geojson" ]; then
      files+=("$INPUT_DIR/counties/${state}_counties.geojson")
    fi
  done

  if [ ${#files[@]} -gt 0 ]; then
    merge_geojson "$OUTPUT_DIR/counties_${region}.geojson" "${files[@]}"
    echo "  ✓ counties_${region}.geojson"
  fi
done

# Merge Cities by Region
echo "=== Merging Cities ==="
for region in "${!REGIONS[@]}"; do
  states="${REGIONS[$region]}"
  files=()
  for state in $states; do
    if [ -f "$INPUT_DIR/cities/${state}_cities.geojson" ]; then
      files+=("$INPUT_DIR/cities/${state}_cities.geojson")
    fi
  done

  if [ ${#files[@]} -gt 0 ]; then
    merge_geojson "$OUTPUT_DIR/cities_${region}.geojson" "${files[@]}"
    echo "  ✓ cities_${region}.geojson"
  fi
done

# Similar for ZCTAs and Tracts...

echo "=== Merge Complete ==="
```

### Upload to Mapbox Tilesets

```bash
#!/bin/bash
# upload_to_mapbox.sh
# Uploads merged GeoJSON to Mapbox as tilesets

set -e

MAPBOX_USERNAME="msrodtn"  # Your Mapbox username
OUTPUT_DIR="./merged_tilesets"

# Ensure Mapbox CLI is authenticated
if [ -z "$MAPBOX_ACCESS_TOKEN" ]; then
  echo "Error: MAPBOX_ACCESS_TOKEN not set"
  exit 1
fi

# Upload function
upload_tileset() {
  local file="$1"
  local tileset_name="$2"
  local tileset_id="${MAPBOX_USERNAME}.${tileset_name}"

  echo "Uploading: $tileset_id"

  # Create tileset source
  tilesets upload-source "$MAPBOX_USERNAME" "$tileset_name" "$file" --replace

  # Create recipe (defines how data is processed)
  cat > "/tmp/recipe_${tileset_name}.json" << EOF
{
  "version": 1,
  "layers": {
    "${tileset_name}": {
      "source": "mapbox://tileset-source/${MAPBOX_USERNAME}/${tileset_name}",
      "minzoom": 0,
      "maxzoom": 14
    }
  }
}
EOF

  # Create or update tileset
  tilesets create "$tileset_id" --recipe "/tmp/recipe_${tileset_name}.json" --name "$tileset_name" 2>/dev/null || \
  tilesets update-recipe "$tileset_id" "/tmp/recipe_${tileset_name}.json"

  # Publish
  tilesets publish "$tileset_id"

  echo "  ✓ Published: $tileset_id"
}

# Upload all merged files
for file in "$OUTPUT_DIR"/*.geojson; do
  filename=$(basename "$file" .geojson)
  upload_tileset "$file" "$filename"
  sleep 2  # Rate limiting
done

echo "=== Upload Complete ==="
echo "Tilesets available at: https://studio.mapbox.com/tilesets/"
```

---

## ArcGIS Demographics Download

For demographic data (population, income), use the ArcGIS Living Atlas:

```bash
#!/bin/bash
# download_demographics.sh
# Downloads ACS demographic data from ArcGIS Living Atlas

set -e

OUTPUT_DIR="./demographic_data"
mkdir -p "$OUTPUT_DIR/population"
mkdir -p "$OUTPUT_DIR/income"

ACS_POP_BASE="https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Total_Population_Boundaries/FeatureServer"
ACS_INC_BASE="https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Median_Income_by_Race_and_Age_Selp_Emp_Boundaries/FeatureServer"

# State FIPS
declare -A STATES=(
  ["AL"]="01" ["AK"]="02" ["AZ"]="04" ["AR"]="05" ["CA"]="06"
  ["CO"]="08" ["CT"]="09" ["DE"]="10" ["DC"]="11" ["FL"]="12"
  ["GA"]="13" ["HI"]="15" ["ID"]="16" ["IL"]="17" ["IN"]="18"
  ["IA"]="19" ["KS"]="20" ["KY"]="21" ["LA"]="22" ["ME"]="23"
  ["MD"]="24" ["MA"]="25" ["MI"]="26" ["MN"]="27" ["MS"]="28"
  ["MO"]="29" ["MT"]="30" ["NE"]="31" ["NV"]="32" ["NH"]="33"
  ["NJ"]="34" ["NM"]="35" ["NY"]="36" ["NC"]="37" ["ND"]="38"
  ["OH"]="39" ["OK"]="40" ["OR"]="41" ["PA"]="42" ["RI"]="44"
  ["SC"]="45" ["SD"]="46" ["TN"]="47" ["TX"]="48" ["UT"]="49"
  ["VT"]="50" ["VA"]="51" ["WA"]="53" ["WV"]="54" ["WI"]="55"
  ["WY"]="56"
)

# Download County Demographics
echo "=== Downloading County Demographics ==="
for state in "${!STATES[@]}"; do
  fips="${STATES[$state]}"

  # Population (Layer 1 = County)
  pop_url="${ACS_POP_BASE}/1/query?where=GEOID%20LIKE%20%27${fips}%25%27&outFields=NAME,GEOID,B01001_001E,Shape__Area&f=geojson&returnGeometry=true&outSR=4326"
  curl -s "$pop_url" -o "$OUTPUT_DIR/population/${state}_county_pop.geojson"

  # Income (Layer 1 = County)
  inc_url="${ACS_INC_BASE}/1/query?where=GEOID%20LIKE%20%27${fips}%25%27&outFields=NAME,GEOID,B19049_001E,Shape__Area&f=geojson&returnGeometry=true&outSR=4326"
  curl -s "$inc_url" -o "$OUTPUT_DIR/income/${state}_county_income.geojson"

  echo "  ✓ $state county demographics"
  sleep 0.5
done

# Download Tract Demographics
echo "=== Downloading Tract Demographics ==="
for state in "${!STATES[@]}"; do
  fips="${STATES[$state]}"

  # Population (Layer 2 = Tract)
  pop_url="${ACS_POP_BASE}/2/query?where=GEOID%20LIKE%20%27${fips}%25%27&outFields=NAME,GEOID,B01001_001E,Shape__Area&f=geojson&returnGeometry=true&outSR=4326"
  curl -s "$pop_url" -o "$OUTPUT_DIR/population/${state}_tract_pop.geojson"

  # Income (Layer 2 = Tract)
  inc_url="${ACS_INC_BASE}/2/query?where=GEOID%20LIKE%20%27${fips}%25%27&outFields=NAME,GEOID,B19049_001E,Shape__Area&f=geojson&returnGeometry=true&outSR=4326"
  curl -s "$inc_url" -o "$OUTPUT_DIR/income/${state}_tract_income.geojson"

  echo "  ✓ $state tract demographics"
  sleep 0.5
done

echo "=== Demographics Download Complete ==="
```

---

## Frontend Configuration

After uploading tilesets, update the frontend configuration:

### `frontend/src/config/boundaryTilesets.ts`

```typescript
// Auto-generated tileset configuration
export const BOUNDARY_TILESETS = {
  // Regional tilesets
  midwest: {
    counties: { id: 'msrodtn.counties_midwest', sourceLayer: 'counties_midwest' },
    cities: { id: 'msrodtn.cities_midwest', sourceLayer: 'cities_midwest' },
    zctas: { id: 'msrodtn.zctas_midwest', sourceLayer: 'zctas_midwest' },
  },
  mountain: {
    counties: { id: 'msrodtn.counties_mountain', sourceLayer: 'counties_mountain' },
    cities: { id: 'msrodtn.cities_mountain', sourceLayer: 'cities_mountain' },
    zctas: { id: 'msrodtn.zctas_mountain', sourceLayer: 'zctas_mountain' },
  },
  // ... add other regions
};

// Helper to get tileset for a state
export function getTilesetForState(state: string): typeof BOUNDARY_TILESETS.midwest {
  const stateToRegion: Record<string, keyof typeof BOUNDARY_TILESETS> = {
    'IA': 'midwest', 'NE': 'midwest', 'MN': 'midwest', 'WI': 'midwest',
    'MT': 'mountain', 'WY': 'mountain', 'CO': 'mountain', 'NV': 'mountain',
    // ... map all states
  };

  return BOUNDARY_TILESETS[stateToRegion[state] || 'midwest'];
}
```

---

## Overnight Automation Script

### `run_full_pipeline.sh`

```bash
#!/bin/bash
# run_full_pipeline.sh
# Complete automation script - run overnight

set -e

LOG_FILE="./boundary_pipeline_$(date +%Y%m%d_%H%M%S).log"

echo "Starting full boundary data pipeline at $(date)" | tee "$LOG_FILE"

# Step 1: Download Census TIGER boundaries
echo "Step 1: Downloading Census TIGER boundaries..." | tee -a "$LOG_FILE"
./download_all_boundaries.sh 2>&1 | tee -a "$LOG_FILE"

# Step 2: Download ZCTAs
echo "Step 2: Downloading ZCTAs..." | tee -a "$LOG_FILE"
./download_zctas.sh 2>&1 | tee -a "$LOG_FILE"

# Step 3: Download ArcGIS demographics
echo "Step 3: Downloading ArcGIS demographics..." | tee -a "$LOG_FILE"
./download_demographics.sh 2>&1 | tee -a "$LOG_FILE"

# Step 4: Merge files by region
echo "Step 4: Merging files..." | tee -a "$LOG_FILE"
./merge_and_upload.sh 2>&1 | tee -a "$LOG_FILE"

# Step 5: Upload to Mapbox
echo "Step 5: Uploading to Mapbox..." | tee -a "$LOG_FILE"
./upload_to_mapbox.sh 2>&1 | tee -a "$LOG_FILE"

# Step 6: Generate frontend config
echo "Step 6: Generating frontend config..." | tee -a "$LOG_FILE"
./generate_frontend_config.sh 2>&1 | tee -a "$LOG_FILE"

echo "Pipeline complete at $(date)" | tee -a "$LOG_FILE"
echo "Log saved to: $LOG_FILE"
```

---

## Troubleshooting

### Common Issues

1. **Rate Limiting**: Add `sleep 0.5` between requests
2. **Large Files**: Split by region, not national
3. **Invalid JSON**: Validate with `jq empty file.geojson`
4. **Mapbox Upload Fails**: Check file size < 300MB per tileset

### API Limits

| Service | Limit | Notes |
|---------|-------|-------|
| Census TIGER | No auth required | ~1 req/sec recommended |
| ArcGIS Living Atlas | No auth required | ~1 req/sec recommended |
| Mapbox Tilesets | 20 uploads/hour | Use --replace for updates |

---

## File Structure

```
boundary_data/
├── counties/
│   ├── AL_counties.geojson
│   ├── AK_counties.geojson
│   └── ... (51 files)
├── cities/
│   └── ... (51 files)
├── zctas/
│   └── ... (51 files)
├── tracts/
│   └── ... (51 files)
demographic_data/
├── population/
│   ├── AL_county_pop.geojson
│   ├── AL_tract_pop.geojson
│   └── ...
├── income/
│   └── ...
merged_tilesets/
├── counties_midwest.geojson
├── cities_midwest.geojson
└── ...
```

---

## Quick Start

```bash
# 1. Clone scripts to project
mkdir -p scripts/boundary_automation
cd scripts/boundary_automation

# 2. Set Mapbox token
export MAPBOX_ACCESS_TOKEN="pk.xxx..."

# 3. Make scripts executable
chmod +x *.sh

# 4. Run overnight pipeline
nohup ./run_full_pipeline.sh > pipeline.log 2>&1 &

# 5. Check progress
tail -f pipeline.log
```

---

## Adding Population Data to Tilesets

Census TIGER boundary files contain geometry only - no demographic data. To display population in hover popups, you must merge Census ACS population data into the GeoJSON before uploading to Mapbox.

### Python Script: `scripts/add_population_to_tilesets.py`

This script fetches population from the Census ACS API and merges it with existing boundary GeoJSON files:

```python
#!/usr/bin/env python3
"""
Add population data to Cities and ZCTAs GeoJSON files.

This script:
1. Fetches population data from Census ACS API
2. Merges it with existing boundary GeoJSON files
3. Outputs new GeoJSON files ready for Mapbox upload
"""

import json
import httpx
import asyncio
from pathlib import Path

# Census API base URL (no key required for basic queries)
CENSUS_API_BASE = "https://api.census.gov/data/2022/acs/acs5"

# State FIPS codes for target markets
STATE_FIPS = {
    "IA": "19",
    "NE": "31",
    "NV": "32",
    "ID": "16",
}

async def fetch_city_population(state_fips: str) -> dict:
    """Fetch population for all places (cities) in a state from Census ACS."""
    url = f"{CENSUS_API_BASE}"
    params = {
        "get": "NAME,B01001_001E",  # NAME and Total Population
        "for": "place:*",
        "in": f"state:{state_fips}",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # First row is headers: ['NAME', 'B01001_001E', 'state', 'place']
        result = {}
        for row in data[1:]:
            name, pop, state, place = row
            geoid = f"{state}{place}"  # Full GEOID for places
            try:
                result[geoid] = int(pop) if pop else 0
            except (ValueError, TypeError):
                result[geoid] = 0
        return result

async def fetch_zcta_population() -> dict:
    """Fetch population for all ZCTAs from Census ACS."""
    url = f"{CENSUS_API_BASE}"
    params = {
        "get": "NAME,B01001_001E",
        "for": "zip code tabulation area:*",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        result = {}
        for row in data[1:]:
            name, pop, zcta = row
            try:
                result[zcta] = int(pop) if pop else 0
            except (ValueError, TypeError):
                result[zcta] = 0
        return result
```

### Running the Script

```bash
# Install dependencies
pip install httpx

# Run the script
cd csoki-site-selection
python scripts/add_population_to_tilesets.py
```

**Output:**
```
============================================================
Adding Population Data to Boundary Tilesets
============================================================
Fetching city population data from Census ACS...
  Fetching IA (19)...
    Found 1027 cities
  ...
Total city populations fetched: 1987
Matched 1987 of 1987 cities with population data
Saved to mapbox-tilesets/cities_with_pop.geojson

Fetching ZCTA population data from Census ACS...
Total ZCTA populations fetched: 33774
Matched 2300 of 2300 ZCTAs with population data
Saved to mapbox-tilesets/zctas_with_pop.geojson
```

### Uploading Updated Tilesets

**Important:** Mapbox allows in-place replacement of tilesets. The tileset ID stays the same, preserving all your map configurations.

#### Option 1: Mapbox Studio (Recommended)
1. Go to [https://studio.mapbox.com/tilesets/](https://studio.mapbox.com/tilesets/)
2. Click on your existing tileset (e.g., `msrodtn.9jpdhu14`)
3. Click **"Replace"** and upload the new GeoJSON
4. The source-layer name may change - check in Mapbox Studio

#### Option 2: Mapbox Tilesets CLI
```bash
export MAPBOX_ACCESS_TOKEN="your_token_here"

# Upload Cities with population
tilesets upload-source msrodtn cities_with_pop mapbox-tilesets/cities_with_pop.geojson
tilesets publish msrodtn.9jpdhu14

# Upload ZCTAs with population
tilesets upload-source msrodtn zctas_with_pop mapbox-tilesets/zctas_with_pop.geojson
tilesets publish msrodtn.917bnr7e
```

### Updating Frontend Configuration

After uploading, check Mapbox Studio for the new **source-layer** name. If it changed, update `MapboxMap.tsx`:

```typescript
const BOUNDARY_TILESETS = {
  counties: {
    id: 'msrodtn.05vjtaqc',
    sourceLayer: 'counties-aukpeg',  // From Mapbox Studio
  },
  cities: {
    id: 'msrodtn.9jpdhu14',
    sourceLayer: 'cities_with_pop-xxxxx',  // May change after upload!
  },
  zctas: {
    id: 'msrodtn.917bnr7e',
    sourceLayer: 'zctas_with_pop-xxxxx',   // May change after upload!
  },
};
```

### GeoJSON Property Format

After merging, each feature will have a `POPULATION` property:

**Cities GeoJSON:**
```json
{
  "type": "Feature",
  "properties": {
    "STATEFP": "19",
    "PLACEFP": "21000",
    "GEOID": "1921000",
    "NAME": "Des Moines",
    "POPULATION": 214237
  },
  "geometry": { ... }
}
```

**ZCTAs GeoJSON:**
```json
{
  "type": "Feature",
  "properties": {
    "ZCTA5CE20": "50301",
    "GEOID20": "50301",
    "POPULATION": 12543
  },
  "geometry": { ... }
}
```

---

## Frontend Hover Integration

The frontend reads the `POPULATION` property from tileset features on hover:

### Mouse Handler (MapboxMap.tsx)

```typescript
// Handle city boundaries layer (tileset)
if (map.getLayer('city-boundaries-fill')) {
  const features = map.queryRenderedFeatures(e.point, {
    layers: ['city-boundaries-fill'],
  });

  if (features && features.length > 0) {
    const feature = features[0];
    const cityId = feature.properties?.NAME || feature.properties?.BASENAME || null;
    setHoveredCityId(cityId);

    setHoveredCityInfo({
      name: cityId || 'Unknown City',
      population: feature.properties?.POPULATION || 0,  // Read from tileset
      lngLat: [e.lngLat.lng, e.lngLat.lat],
    });
    return;
  }
}
```

### Layer Paint Expressions for Hover Highlighting

```typescript
<Layer
  id="city-boundaries-fill"
  type="fill"
  source-layer={BOUNDARY_TILESETS.cities.sourceLayer}
  minzoom={6}
  paint={{
    'fill-color': '#22C55E',
    'fill-opacity': [
      'case',
      ['==', ['get', 'NAME'], hoveredCityId],  // Dynamic hover check
      0.35,  // Hovered
      0.1,   // Normal
    ],
  }}
/>
<Layer
  id="city-boundaries"
  type="line"
  source-layer={BOUNDARY_TILESETS.cities.sourceLayer}
  minzoom={6}
  paint={{
    'line-color': '#22C55E',
    'line-width': [
      'case',
      ['==', ['get', 'NAME'], hoveredCityId],
      4,     // Hovered
      ['interpolate', ['linear'], ['zoom'], 6, 1, 10, 1.5, 14, 2],
    ],
    'line-opacity': [
      'case',
      ['==', ['get', 'NAME'], hoveredCityId],
      1,     // Hovered
      0.9,   // Normal
    ],
  }}
/>
```

### Popup Display

```typescript
{hoveredCityInfo && (
  <Popup
    longitude={hoveredCityInfo.lngLat[0]}
    latitude={hoveredCityInfo.lngLat[1]}
    closeButton={false}
    closeOnClick={false}
    anchor="bottom"
    offset={10}
    className="!z-[100]"  // Above markers
  >
    <div className="text-sm min-w-[140px]">
      <div className="font-semibold text-green-700 mb-1">
        {hoveredCityInfo.name}
      </div>
      {hoveredCityInfo.population > 0 && (
        <div className="text-xs text-gray-600">
          Pop: {hoveredCityInfo.population.toLocaleString()}
        </div>
      )}
    </div>
  </Popup>
)}
```

---

## Notes

- **Data Freshness**: Census TIGER updates annually; ArcGIS Living Atlas updates with new ACS releases
- **Storage**: Full US data ~2-5GB raw, ~500MB-1GB as tilesets
- **Processing Time**: ~2-4 hours for full US download + upload
- **Cost**: All data sources are free; Mapbox tileset hosting included in free tier up to 20 tilesets
- **Population Data**: Census ACS 5-year estimates (2022) - updated annually
