#!/usr/bin/env bash
#
# Upload national boundary GeoJSON/NDJSON files to Mapbox as tilesets.
#
# Prerequisites:
#   1. Install Mapbox Tilesets CLI: pip install mapbox-tilesets
#   2. Set MAPBOX_SECRET_TOKEN env var (needs tilesets:write + uploads:write scopes)
#      Get one at: https://account.mapbox.com/access-tokens/
#      Must be a SECRET token (starts with sk.eyJ1Ijoi...)
#
# Usage:
#   export MAPBOX_SECRET_TOKEN="sk.eyJ1Ijoi..."
#   bash scripts/upload_national_tilesets.sh
#
# Output:
#   4 Mapbox tilesets:
#     msrodtn.national-counties
#     msrodtn.national-cities
#     msrodtn.national-zctas
#     msrodtn.national-tracts

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
    echo "  bash scripts/upload_national_tilesets.sh"
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
echo "National Boundary Tileset Upload"
echo "============================================================"
echo "Data directory: $DATA_DIR"
echo "Username: $MAPBOX_USERNAME"
echo ""

# ----------------------------------------------------------------
# Define tilesets and their source files
# ----------------------------------------------------------------
declare -A TILESET_FILES=(
    ["national-counties"]="national_counties.geojson"
    ["national-cities"]="national_cities.geojson"
    ["national-zctas"]="national_zctas.geojson"
    ["national-tracts"]="national_tracts.ndjson"
)

declare -A TILESET_NAMES=(
    ["national-counties"]="National Counties"
    ["national-cities"]="National Cities"
    ["national-zctas"]="National ZCTAs"
    ["national-tracts"]="National Census Tracts"
)

# ----------------------------------------------------------------
# Create recipe files
# ----------------------------------------------------------------
echo "Creating tileset recipes..."

# Counties recipe - preserve key demographic properties
cat > "$RECIPE_DIR/national-counties.json" << 'RECIPE'
{
  "version": 1,
  "layers": {
    "national_counties": {
      "source": "mapbox://tileset-source/msrodtn/national-counties",
      "minzoom": 2,
      "maxzoom": 12,
      "features": {
        "attributes": {
          "allowed_output": [
            "NAME", "GEOID", "POPULATION", "MEDIAN_INCOME", "POP_DENSITY"
          ]
        }
      }
    }
  }
}
RECIPE

# Cities recipe
cat > "$RECIPE_DIR/national-cities.json" << 'RECIPE'
{
  "version": 1,
  "layers": {
    "national_cities": {
      "source": "mapbox://tileset-source/msrodtn/national-cities",
      "minzoom": 4,
      "maxzoom": 14,
      "features": {
        "attributes": {
          "allowed_output": [
            "NAME", "GEOID", "POPULATION", "STATE", "ALAND"
          ]
        }
      }
    }
  }
}
RECIPE

# ZCTAs recipe
cat > "$RECIPE_DIR/national-zctas.json" << 'RECIPE'
{
  "version": 1,
  "layers": {
    "national_zctas": {
      "source": "mapbox://tileset-source/msrodtn/national-zctas",
      "minzoom": 4,
      "maxzoom": 14,
      "features": {
        "attributes": {
          "allowed_output": [
            "NAME", "GEOID20", "ZCTA5CE20", "POPULATION", "ALAND20"
          ]
        }
      }
    }
  }
}
RECIPE

# Census Tracts recipe
cat > "$RECIPE_DIR/national-tracts.json" << 'RECIPE'
{
  "version": 1,
  "layers": {
    "national_tracts": {
      "source": "mapbox://tileset-source/msrodtn/national-tracts",
      "minzoom": 4,
      "maxzoom": 14,
      "features": {
        "attributes": {
          "allowed_output": [
            "NAME", "GEOID", "POPULATION", "MEDIAN_INCOME", "POP_DENSITY"
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
# Upload each tileset
# ----------------------------------------------------------------
for tileset_key in national-counties national-cities national-zctas national-tracts; do
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
echo "Next steps:"
echo "1. Check tileset status in Mapbox Studio:"
echo "   https://studio.mapbox.com/tilesets/"
echo ""
echo "2. Note the source-layer names from each tileset's details page."
echo "   They should match the recipe layer names:"
echo "   - national_counties"
echo "   - national_cities"
echo "   - national_zctas"
echo "   - national_tracts"
echo ""
echo "3. Update BOUNDARY_TILESETS in MapboxMap.tsx with the actual"
echo "   tileset IDs and source-layer names if they differ."
echo ""
echo "4. Test by toggling boundary layers at various zoom levels."
