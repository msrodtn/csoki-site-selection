# How to Add Traffic Count Overlay

Simple 3-step process to add Iowa traffic data to the map.

## Step 1: Download Data

```bash
node scripts/download-iowa-traffic.js
```

Creates `data/iowa-traffic.geojson` with ~7,000 road segments.

## Step 2: Upload to Mapbox

```bash
# Install CLI
npm install -g @mapbox/mapbox-sdk-cli

# Set token (get from https://account.mapbox.com/access-tokens/ - needs uploads:write scope)
export MAPBOX_ACCESS_TOKEN=sk.ey...

# Upload
mapbox upload YOUR_USERNAME.iowa-traffic data/iowa-traffic.geojson
```

Replace `YOUR_USERNAME` with your Mapbox username.

## Step 3: Add to Map

Edit `frontend/src/components/Map/MapboxMap.tsx`, find the isochrone layer, and add after it:

```tsx
{/* Iowa Traffic Counts - TODO: Replace YOUR_USERNAME */}
<Source id="iowa-traffic" type="vector" url="mapbox://YOUR_USERNAME.iowa-traffic">
  <Layer
    id="traffic-layer"
    source-layer="iowa-traffic"
    type="line"
    minzoom={8}
    paint={{
      'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 12, 2, 16, 4],
      'line-color': [
        'step',
        ['get', 'AADT'],
        '#00C5FF', 1000,
        '#55FF00', 2000,
        '#FFAA00', 5000,
        '#FF0000'
      ],
      'line-opacity': 0.8,
    }}
  />
</Source>
```

Deploy. Done.

## Verify

Zoom into Des Moines - you should see color-coded roads (blue/green/orange/red by traffic volume).
