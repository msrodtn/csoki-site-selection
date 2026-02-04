# Railway Configuration

## Environment Variables

### Frontend Service

Required environment variables for the frontend service:

- **VITE_MAPBOX_TOKEN**: Your Mapbox access token (pk.ey...)
- **BACKEND_URL**: URL to the backend service (e.g., `https://csoki-backend.up.railway.app`)

### Backend Service

No additional environment variables required beyond what's auto-configured by Railway.

## Service URLs

Set the `BACKEND_URL` in the frontend service to point to your backend service's Railway URL.

Example:
```
BACKEND_URL=https://csoki-site-selection-backend-production.up.railway.app
```

Make sure **NOT** to include `/api` at the end - the frontend nginx config will append that automatically.
