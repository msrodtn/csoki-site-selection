#!/usr/bin/env python3
"""
Re-geocode all stores using Google Geocoding API for precise coordinates.

Usage:
    python scripts/regeocode_google.py

Requires GOOGLE_PLACES_API_KEY environment variable.
"""

import os
import sys
import time
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def geocode_address(address: str, api_key: str) -> tuple[float, float] | None:
    """
    Geocode an address using Google Geocoding API.
    Returns (latitude, longitude) or None if failed.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "OK" and data["results"]:
            location = data["results"][0]["geometry"]["location"]
            return (location["lat"], location["lng"])
        else:
            print(f"  Geocoding failed: {data.get('status', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"  Geocoding error: {e}")
        return None


def main():
    # Get API key
    api_key = settings.GOOGLE_PLACES_API_KEY
    if not api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set in environment")
        sys.exit(1)

    print(f"Using API key: {api_key[:10]}...")

    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Fetch all stores
        result = session.execute(text("""
            SELECT id, street, city, state, postal_code, latitude, longitude
            FROM stores
            ORDER BY id
        """))
        stores = result.fetchall()

        print(f"\nFound {len(stores)} stores to re-geocode")
        print("=" * 60)

        updated = 0
        failed = 0
        skipped = 0

        for i, store in enumerate(stores):
            store_id, street, city, state, postal_code, old_lat, old_lng = store

            # Build full address
            parts = []
            if street:
                parts.append(street)
            if city:
                parts.append(city)
            if state:
                parts.append(state)
            if postal_code:
                parts.append(postal_code)
            parts.append("USA")

            address = ", ".join(parts)

            print(f"\n[{i+1}/{len(stores)}] Store #{store_id}")
            print(f"  Address: {address}")
            print(f"  Old coords: ({old_lat}, {old_lng})")

            # Skip if no address components
            if not street and not city:
                print(f"  SKIPPED: No address")
                skipped += 1
                continue

            # Geocode
            coords = geocode_address(address, api_key)

            if coords:
                new_lat, new_lng = coords
                print(f"  New coords: ({new_lat}, {new_lng})")

                # Calculate distance moved (rough estimate in meters)
                if old_lat and old_lng:
                    lat_diff = abs(new_lat - old_lat) * 111000  # ~111km per degree
                    lng_diff = abs(new_lng - old_lng) * 85000   # ~85km per degree at mid-latitudes
                    dist = (lat_diff**2 + lng_diff**2) ** 0.5
                    print(f"  Moved: ~{dist:.0f} meters")

                # Update database (only lat/lng - PostGIS location column may not exist)
                session.execute(text("""
                    UPDATE stores
                    SET latitude = :lat,
                        longitude = :lng
                    WHERE id = :id
                """), {"lat": new_lat, "lng": new_lng, "id": store_id})

                updated += 1
            else:
                failed += 1

            # Rate limiting - Google allows 50 QPS but let's be conservative
            time.sleep(0.1)

            # Commit every 100 stores
            if (i + 1) % 100 == 0:
                session.commit()
                print(f"\n--- Committed {i+1} stores ---")

        # Final commit
        session.commit()

        print("\n" + "=" * 60)
        print(f"COMPLETE!")
        print(f"  Updated: {updated}")
        print(f"  Failed:  {failed}")
        print(f"  Skipped: {skipped}")
        print(f"  Total:   {len(stores)}")

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
