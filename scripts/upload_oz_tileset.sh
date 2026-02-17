#!/usr/bin/env bash
#
# Upload Opportunity Zone tilesets to Mapbox.
#
# Prerequisites:
#   1. Install Mapbox Tilesets CLI: pip install mapbox-tilesets
#   2. Set MAPBOX_SECRET_TOKEN env var (needs tilesets:write + uploads:write scopes)
#
# Usage:
#   export MAPBOX_SECRET_TOKEN="sk.eyJ1Ijoi..."
#   bash scripts/upload_oz_tileset.sh
#
# Output:
#   2 Mapbox tilesets:
#     msrodtn.national-oz-tracts       (OZ 1.0 designated)
#     msrodtn.national-oz2-eligible    (OZ 2.0 eligible preview)

set -euo pipefail

MAPBOX_USERNAME="msrodtn"
DATA_DIR="$(cd "$(dirname "$0")/.." && pwd)/mapbox-tilesets"
RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)/tileset-recipes"

# Check for secret token
if [ -z "${MAPBOX_SECRET_TOKEN:-}" ]; then
    echo "ERROR: MAPBOX_SECRET_TOKEN environment variable is not set."
    echo ""
    echo "You need a Mapbox secret token with these scopes:"
    echo "  - tilesets:write"
    echo "  - uploads:write"
    echo ""
    echo "Get one at: https://account.mapbox.com/access-tokens/"
    echo "The token must start with 'sk.eyJ1Ijoi...'"
    echo ""
    echo "Usage:"
    echo "  export MAPBOX_SECRET_TOKEN=\"sk.eyJ1Ijoi...\""
    echo "  bash scripts/upload_oz_tileset.sh"
    exit 1
fi

# Check for tilesets CLI
if ! command -v tilesets &> /dev/null; then
    echo "ERROR: Mapbox Tilesets CLI not found."
    echo "Install with: pip install mapbox-tilesets"
    exit 1
fi

# Export token for tilesets CLI
export MAPBOX_ACCESS_TOKEN="$MAPBOX_SECRET_TOKEN"

# Create recipe directory
mkdir -p "$RECIPE_DIR"

echo "============================================================"
echo "Opportunity Zones Tileset Upload"
echo "============================================================"
echo "Data directory: $DATA_DIR"
echo "Username: $MAPBOX_USERNAME"
echo ""

# ----------------------------------------------------------------
# Create recipe files
# ----------------------------------------------------------------
echo "Creating tileset recipes..."

# OZ 1.0 Designated Tracts recipe
cat > "$RECIPE_DIR/national-oz-tracts.json" << 'RECIPE'
{
  "version": 1,
  "layers": {
    "national_oz_tracts": {
      "source": "mapbox://tileset-source/msrodtn/national-oz-tracts",
      "minzoom": 2,
      "maxzoom": 14,
      "features": {
        "attributes": {
          "allowed_output": [
            "GEOID10", "STATE", "COUNTY", "TRACT", "STUSAB", "STATE_NAME", "OZ_VERSION"
          ]
        }
      }
    }
  }
}
RECIPE

# OZ 2.0 Eligible Tracts recipe
cat > "$RECIPE_DIR/national-oz2-eligible.json" << 'RECIPE'
{
  "version": 1,
  "layers": {
    "national_oz2_eligible": {
      "source": "mapbox://tileset-source/msrodtn/national-oz2-eligible",
      "minzoom": 4,
      "maxzoom": 14,
      "features": {
        "attributes": {
          "allowed_output": [
            "GEOID", "STATE", "COUNTY", "TRACT", "STATE_NAME", "ELIGIBLE_STATUS"
          ]
        }
      }
    }
  }
}
RECIPE

echo "  Recipes saved to $RECIPE_DIR/"
echo ""

# ----------------------------------------------------------------
# Define tilesets
# ----------------------------------------------------------------
declare -A TILESET_FILES=(
    ["national-oz-tracts"]="national_oz_tracts.ndjson"
    ["national-oz2-eligible"]="national_oz2_eligible.ndjson"
)

declare -A TILESET_NAMES=(
    ["national-oz-tracts"]="National Opportunity Zones 1.0"
    ["national-oz2-eligible"]="National OZ 2.0 Eligible Tracts"
)

# ----------------------------------------------------------------
# Upload each tileset
# ----------------------------------------------------------------
for tileset_key in national-oz-tracts national-oz2-eligible; do
    source_file="${TILESET_FILES[$tileset_key]}"
    tileset_name="${TILESET_NAMES[$tileset_key]}"
    tileset_id="${MAPBOX_USERNAME}.${tileset_key}"
    source_path="${DATA_DIR}/${source_file}"
    recipe_path="${RECIPE_DIR}/${tileset_key}.json"

    echo "------------------------------------------------------------"
    echo "Processing: $tileset_name ($tileset_key)"
    echo "------------------------------------------------------------"

    # Check if source file exists
    if [ ! -f "$source_path" ]; then
        echo "  WARNING: Source file not found: $source_path"
        echo "  Skipping $tileset_key..."
        echo ""
        continue
    fi

    file_size=$(du -h "$source_path" | cut -f1)
    echo "  Source file: $source_path ($file_size)"

    # Step 1: Upload source data
    echo "  [1/3] Uploading tileset source..."
    if tilesets upload-source --replace "$MAPBOX_USERNAME" "$tileset_key" "$source_path"; then
        echo "  Source uploaded successfully."
    else
        echo "  ERROR: Failed to upload source for $tileset_key"
        echo "  Skipping..."
        echo ""
        continue
    fi

    # Step 2: Create tileset (or update recipe if it already exists)
    echo "  [2/3] Creating/updating tileset..."
    if tilesets create "$tileset_id" --recipe "$recipe_path" --name "$tileset_name" 2>/dev/null; then
        echo "  Tileset created: $tileset_id"
    else
        echo "  Tileset may already exist, updating recipe..."
        tilesets update-recipe "$tileset_id" "$recipe_path" || true
    fi

    # Step 3: Publish tileset
    echo "  [3/3] Publishing tileset..."
    if tilesets publish "$tileset_id"; then
        echo "  Published successfully!"
    else
        echo "  ERROR: Failed to publish $tileset_id"
    fi

    echo ""
done

echo "============================================================"
echo "UPLOAD COMPLETE"
echo "============================================================"
echo ""
echo "Tilesets:"
echo "  - msrodtn.national-oz-tracts       (OZ 1.0 designated)"
echo "  - msrodtn.national-oz2-eligible    (OZ 2.0 eligible preview)"
echo ""
echo "Next steps:"
echo "1. Check tileset status in Mapbox Studio:"
echo "   https://studio.mapbox.com/tilesets/"
echo ""
echo "2. Verify source-layer names match:"
echo "   - national_oz_tracts"
echo "   - national_oz2_eligible"
echo ""
echo "3. The frontend OZ_TILESETS config in MapboxMap.tsx should work"
echo "   automatically with these tileset IDs."
