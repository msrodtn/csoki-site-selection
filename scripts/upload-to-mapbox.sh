#!/bin/bash
# Upload Traffic Data to Mapbox Tilesets
#
# Prerequisites:
#   - npm install -g @mapbox/mapbox-sdk-cli
#   - export MAPBOX_ACCESS_TOKEN=sk.ey...
#
# Usage:
#   ./upload-to-mapbox.sh IA your-username
#   ./upload-to-mapbox.sh NE your-username

set -e

STATE=$1
USERNAME=$2

if [ -z "$STATE" ] || [ -z "$USERNAME" ]; then
  echo "Usage: ./upload-to-mapbox.sh <STATE_CODE> <MAPBOX_USERNAME>"
  echo ""
  echo "Example:"
  echo "  ./upload-to-mapbox.sh IA myusername"
  echo ""
  exit 1
fi

if [ -z "$MAPBOX_ACCESS_TOKEN" ]; then
  echo "❌ Error: MAPBOX_ACCESS_TOKEN not set"
  echo ""
  echo "Get your token from: https://account.mapbox.com/access-tokens/"
  echo "Then run: export MAPBOX_ACCESS_TOKEN=sk.ey..."
  echo ""
  exit 1
fi

STATE_LOWER=$(echo "$STATE" | tr '[:upper:]' '[:lower:]')
GEOJSON_FILE="data/traffic/${STATE_LOWER}-traffic.geojson"
TILESET_ID="${USERNAME}.${STATE_LOWER}-traffic"
SOURCE_ID="${STATE_LOWER}-traffic"

echo "📦 Uploading $STATE traffic data to Mapbox..."
echo ""

# Check if file exists
if [ ! -f "$GEOJSON_FILE" ]; then
  echo "❌ File not found: $GEOJSON_FILE"
  echo ""
  echo "Run this first:"
  echo "  node scripts/download-traffic-data.js $STATE"
  echo ""
  exit 1
fi

echo "1️⃣ Uploading tileset source..."
mapbox tilesets upload-source "$USERNAME" "$SOURCE_ID" "$GEOJSON_FILE"

echo ""
echo "2️⃣ Creating tileset recipe..."
cat > "/tmp/${STATE_LOWER}-traffic-recipe.json" << EOF
{
  "version": 1,
  "layers": {
    "traffic": {
      "source": "mapbox://tileset-source/${USERNAME}/${SOURCE_ID}",
      "minzoom": 6,
      "maxzoom": 14
    }
  }
}
EOF

echo ""
echo "3️⃣ Creating tileset: $TILESET_ID"
mapbox tilesets create "$TILESET_ID" \
  --recipe "/tmp/${STATE_LOWER}-traffic-recipe.json" \
  --name "$STATE Traffic Counts" \
  --description "Annual Average Daily Traffic (AADT) from ${STATE} DOT" \
  || echo "ℹ️  Tileset already exists, updating..."

echo ""
echo "4️⃣ Publishing tileset..."
mapbox tilesets publish "$TILESET_ID"

echo ""
echo "✅ Done!"
echo ""
echo "📍 Your tileset URL:"
echo "   mapbox://${TILESET_ID}"
echo ""
echo "🎨 View in Mapbox Studio:"
echo "   https://studio.mapbox.com/tilesets/${TILESET_ID}/"
echo ""
echo "🔧 Use in frontend:"
echo "   <Source type=\"vector\" url=\"mapbox://${TILESET_ID}\">"
echo "     <Layer source-layer=\"traffic\" ... />"
echo "   </Source>"
echo ""
