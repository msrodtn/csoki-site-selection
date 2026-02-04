#!/bin/sh

# Inject runtime environment variables into a config file
# This allows Railway environment variables to work without rebuilding

MAPBOX_TOKEN="${VITE_MAPBOX_TOKEN:-$VITE_MAPBOX_ACCESS_TOKEN}"

cat > /usr/share/nginx/html/runtime-config.js << EOF
window.RUNTIME_CONFIG = {
  MAPBOX_TOKEN: "${MAPBOX_TOKEN}"
};
EOF

echo "Runtime config created with Mapbox token: ${MAPBOX_TOKEN:0:20}..."

# Start nginx
exec nginx -g 'daemon off;'
