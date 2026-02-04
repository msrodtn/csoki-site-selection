#!/bin/sh

# Inject runtime environment variables into a config file
# This allows Railway environment variables to work without rebuilding

MAPBOX_TOKEN="${VITE_MAPBOX_TOKEN:-$VITE_MAPBOX_ACCESS_TOKEN}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

cat > /usr/share/nginx/html/runtime-config.js << EOF
window.RUNTIME_CONFIG = {
  MAPBOX_TOKEN: "${MAPBOX_TOKEN}"
};
EOF

echo "Runtime config created with Mapbox token: ${MAPBOX_TOKEN:0:20}..."
echo "Backend URL: ${BACKEND_URL}"

# Replace BACKEND_URL placeholder in nginx config
sed -i "s|BACKEND_URL_PLACEHOLDER|${BACKEND_URL}|g" /etc/nginx/conf.d/default.conf

# Start nginx
exec nginx -g 'daemon off;'
