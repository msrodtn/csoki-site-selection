# Traffic Count Overlay Feature

Display state DOT traffic count data (AADT - Annual Average Daily Traffic) on the map.

## Current Status

✅ **Working now** - Iowa traffic data via direct ArcGIS fetch  
🚀 **Upgrade path ready** - Switch to Mapbox tilesets for 10x performance

## Quick Start (Works Now)

The map currently fetches Iowa traffic data directly from Iowa DOT's ArcGIS service. Just:

1. Click the **Traffic Count** control (bar chart icon on left sidebar)
2. Select **Iowa**
3. Zoom into Iowa (Des Moines, Cedar Rapids, etc.)
4. See color-coded roads:
   - **Blue**: 0-999 vehicles/day (low traffic)
   - **Green**: 1,000-1,999 vehicles/day (moderate)
   - **Orange**: 2,000-4,999 vehicles/day (high)
   - **Red**: 5,000+ vehicles/day (very high)

## Upgrade to Mapbox Tilesets (Recommended)

For better performance and scalability:

### Benefits
- ⚡ **10x faster** - vector tiles instead of 5 MB GeoJSON
- 📦 **No limits** - handles millions of features (vs 2,000 max)
- 🎨 **Visual styling** - edit colors in Mapbox Studio
- 🌍 **Scales globally** - add unlimited states

### Setup (15 minutes)

**1. Install Mapbox CLI**
```bash
npm install -g @mapbox/mapbox-sdk-cli
```

**2. Get Mapbox token**
- Go to https://account.mapbox.com/access-tokens/
- Create a token with `uploads:write` scope (starts with `sk.`)
```bash
export MAPBOX_ACCESS_TOKEN=sk.ey...
```

**3. Download Iowa traffic data**
```bash
node scripts/download-traffic-data.js IA
```

**4. Upload to Mapbox**
```bash
./scripts/upload-to-mapbox.sh IA your-username
```
Replace `your-username` with your Mapbox username.

**5. Update frontend config**

Edit `frontend/src/config/traffic-sources.ts`:

```typescript
// Change this:
export const TRAFFIC_SOURCE_MODE: TrafficSourceMode = 'arcgis';

// To this:
export const TRAFFIC_SOURCE_MODE: TrafficSourceMode = 'tileset';

// And update the tileset URL:
export const TILESET_SOURCES = {
  IA: {
    name: 'Iowa',
    url: 'mapbox://your-username.ia-traffic',  // Your actual tileset ID
    sourceLayer: 'traffic',
  },
};
```

**6. Deploy**
```bash
git add .
git commit -m "Switch to Mapbox tilesets for traffic data"
git push
```

Done! Traffic data now loads 10x faster from Mapbox's CDN.

## Adding More States

### Find the ArcGIS Service

Google: `"[State] DOT" traffic counts ArcGIS REST`

Look for URLs like:
- `https://gis.iowa.gov/.../FeatureServer/X`
- `https://nebraskatransportation.com/.../MapServer/X`

### Add to Config

**Option A: ArcGIS Mode (Quick)**

Edit `frontend/src/config/traffic-sources.ts`:

```typescript
export const ARCGIS_SOURCES = {
  IA: { ... },
  NE: {
    name: 'Nebraska',
    url: 'https://gis.nebraska.gov/.../FeatureServer/10',
    fields: 'AADT,ROUTE,YEAR',
    maxRecords: 2000,
  },
};
```

**Option B: Tileset Mode (Better)**

```bash
# Add to download script
# Edit scripts/download-traffic-data.js and add NE to STATE_SERVICES

# Download
node scripts/download-traffic-data.js NE

# Upload
./scripts/upload-to-mapbox.sh NE your-username

# Update config
# Add to TILESET_SOURCES in traffic-sources.ts
```

## Updating Data

Traffic data refreshes monthly/quarterly. To update:

```bash
# Re-download
node scripts/download-traffic-data.js IA

# Re-upload (tileset mode only)
./scripts/upload-to-mapbox.sh IA your-username
```

Changes appear on the map within 15 minutes.

## Architecture

### Current (ArcGIS Mode)
```
State DOT ArcGIS → Frontend (runtime fetch) → 5 MB GeoJSON → Render on map
                     └─ 2-10 seconds load time
```

### Upgraded (Tileset Mode)
```
State DOT ArcGIS → Download Script → Upload to Mapbox → Vector Tiles (CDN)
                                                          └─ Frontend (instant load)
```

## Files

- `frontend/src/config/traffic-sources.ts` - Traffic data configuration
- `frontend/src/components/Map/TrafficCountControl.tsx` - UI control
- `scripts/download-traffic-data.js` - Download traffic from state DOTs
- `scripts/upload-to-mapbox.sh` - Upload to Mapbox tilesets
- `MAPBOX_TILESETS.md` - Detailed tileset documentation

## Troubleshooting

**No traffic data showing?**
- Make sure you're zoomed into the state (zoom level 8+)
- Check browser console for errors
- Verify the state is selected in the control

**Want to switch back to ArcGIS mode?**
- Change `TRAFFIC_SOURCE_MODE` to `'arcgis'` in `traffic-sources.ts`
- No other changes needed - supports both modes

**Questions?**
See `MAPBOX_TILESETS.md` for detailed documentation.
