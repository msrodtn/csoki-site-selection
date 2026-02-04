# Mapbox Tilesets for Traffic Data

## Why Tilesets?

**Current (Direct Fetch):**
- ❌ Fetches 2-5 MB on every load
- ❌ Limited to 2,000 features per request
- ❌ Slow rendering on client
- ❌ Can't handle millions of features

**With Tilesets:**
- ✅ **10x faster** - vector tiles served from CDN
- ✅ **Scales to millions** - no feature limits
- ✅ **Better performance** - server-side rendering
- ✅ **Visual styling** - use Mapbox Studio editor
- ✅ **Free tier** - 750k tile requests/month

## Setup (One-Time)

### 1. Install Mapbox CLI

```bash
npm install -g @mapbox/mapbox-sdk-cli
```

### 2. Authenticate

```bash
export MAPBOX_ACCESS_TOKEN=sk.ey...  # Your secret token (starts with sk.)
```

Get your secret token from: https://account.mapbox.com/access-tokens/

### 3. Download Traffic Data

```bash
node scripts/download-traffic-data.js IA
```

This creates: `data/traffic/ia-traffic.geojson`

### 4. Upload to Mapbox

**Option A: Using CLI (Recommended)**

```bash
# Upload as a tileset source
mapbox tilesets upload-source YOUR_USERNAME ia-traffic data/traffic/ia-traffic.geojson

# Create tileset recipe (one-time)
cat > ia-traffic-recipe.json << EOF
{
  "version": 1,
  "layers": {
    "traffic": {
      "source": "mapbox://tileset-source/YOUR_USERNAME/ia-traffic",
      "minzoom": 6,
      "maxzoom": 14
    }
  }
}
EOF

# Create the tileset
mapbox tilesets create YOUR_USERNAME.ia-traffic --recipe ia-traffic-recipe.json --name "Iowa Traffic Counts"

# Publish the tileset
mapbox tilesets publish YOUR_USERNAME.ia-traffic
```

**Option B: Using Mapbox Studio (Web UI)**

1. Go to https://studio.mapbox.com/tilesets/
2. Click **New tileset**
3. Upload `ia-traffic.geojson`
4. Set zoom levels: 6-14
5. Click **Create tileset**

### 5. Update Frontend Code

Replace the ArcGIS fetch with tileset source:

```tsx
// Before (Direct fetch)
const response = await fetch('https://services.arcgis.com/.../query?...');

// After (Tileset)
<Source
  id="traffic-counts"
  type="vector"
  url="mapbox://YOUR_USERNAME.ia-traffic"
>
  <Layer
    id="traffic-layer"
    source-layer="traffic"  // Important!
    type="line"
    paint={{
      'line-width': 2,
      'line-color': [
        'step',
        ['get', 'aadt'],
        '#00C5FF', 0,
        '#55FF00', 1000,
        '#FFAA00', 2000,
        '#FF0000', 5000,
      ],
    }}
  />
</Source>
```

## Adding More States

### 1. Find the ArcGIS Service

Each state DOT has different service URLs. Google:
```
"Nebraska DOT" traffic counts ArcGIS REST
```

Look for URLs like:
- `https://gis.nebraska.gov/.../FeatureServer/X`
- `https://ndot.maps.arcgis.com/.../MapServer/X`

### 2. Add to Script

Edit `scripts/download-traffic-data.js`:

```javascript
const STATE_SERVICES = {
  IA: { ... },
  NE: {
    name: 'Nebraska',
    url: 'https://gis.nebraska.gov/.../FeatureServer/10',
    fields: 'AADT,ROUTE,YEAR',  // Adjust field names
  },
};
```

### 3. Download & Upload

```bash
node scripts/download-traffic-data.js NE
mapbox tilesets upload-source YOUR_USERNAME ne-traffic data/traffic/ne-traffic.geojson
# ... repeat publish steps
```

## Updating Data

Traffic data updates monthly/quarterly. To refresh:

```bash
# Re-download
node scripts/download-traffic-data.js IA

# Update the source
mapbox tilesets upload-source YOUR_USERNAME ia-traffic data/traffic/ia-traffic.geojson

# Re-publish
mapbox tilesets publish YOUR_USERNAME.ia-traffic
```

Changes appear on the map within ~15 minutes.

## Cost

**Mapbox Free Tier:**
- 750,000 tile requests/month
- Unlimited tilesets (up to 20 GB each)

**Typical usage:**
- 1 user viewing Iowa traffic = ~50 tile requests
- 750k requests = ~15,000 user sessions/month
- **More than enough for this use case**

## Architecture

```
State DOT ArcGIS     →  Download Script    →  GeoJSON File
     ↓
Mapbox Tilesets     →  Vector Tiles (CDN)  →  Frontend Map
     ↑
Mapbox Studio (optional styling)
```

## Next Steps

1. Run `node scripts/download-traffic-data.js IA`
2. Upload to Mapbox using CLI or Studio
3. Update frontend with tileset URL
4. Repeat for other states as needed

Questions? See: https://docs.mapbox.com/help/tutorials/get-started-tilesets-api/
