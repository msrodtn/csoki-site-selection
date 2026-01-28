import time
import logging
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses to lat/lng coordinates."""

    def __init__(self):
        self.geolocator = Nominatim(user_agent=settings.GEOCODING_USER_AGENT)
        self.rate_limit = settings.GEOCODING_RATE_LIMIT
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def geocode_address(
        self,
        street: str,
        city: str,
        state: str,
        postal_code: str,
        retries: int = 3
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode a full address to latitude/longitude.

        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails.
        """
        # Build address string
        address_parts = [street, city, state, postal_code, "USA"]
        full_address = ", ".join(filter(None, address_parts))

        for attempt in range(retries):
            try:
                self._rate_limit()
                location = self.geolocator.geocode(full_address, timeout=10)

                if location:
                    logger.debug(f"Geocoded '{full_address}' -> ({location.latitude}, {location.longitude})")
                    return (location.latitude, location.longitude)
                else:
                    # Try with just city, state, zip if full address fails
                    fallback_address = f"{city}, {state} {postal_code}, USA"
                    self._rate_limit()
                    location = self.geolocator.geocode(fallback_address, timeout=10)
                    if location:
                        logger.debug(f"Geocoded (fallback) '{fallback_address}' -> ({location.latitude}, {location.longitude})")
                        return (location.latitude, location.longitude)

                    logger.warning(f"Could not geocode: {full_address}")
                    return None

            except GeocoderTimedOut:
                logger.warning(f"Geocoding timeout for '{full_address}', attempt {attempt + 1}/{retries}")
                time.sleep(2 ** attempt)  # Exponential backoff

            except GeocoderServiceError as e:
                logger.error(f"Geocoding service error: {e}")
                time.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"Unexpected geocoding error: {e}")
                return None

        logger.error(f"Failed to geocode after {retries} attempts: {full_address}")
        return None


# Singleton instance
geocoding_service = GeocodingService()
