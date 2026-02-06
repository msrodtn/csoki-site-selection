import csv
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.store import Store
from app.services.geocoding import geocoding_service

logger = logging.getLogger(__name__)

# Mapping of CSV files to brand names
BRAND_FILE_MAPPING = {
    "csoki_all_stores.csv": "csoki",
    "russell_cellular_all_stores.csv": "russell_cellular",
    "verizon_corporate_stores.csv": "verizon_corporate",
    "victra_stores.csv": "victra",
    "tmobile_stores.csv": "tmobile",
    "uscellular_stores.csv": "uscellular",
    "wireless_zone_stores.csv": "wireless_zone",
    "tcc_stores.csv": "tcc",
}


def import_csv_to_db(
    db: Session,
    csv_path: Path,
    brand: str,
    geocode: bool = False,
    skip_existing: bool = True
) -> dict:
    """
    Import stores from a CSV file into the database.

    Args:
        db: Database session
        csv_path: Path to CSV file
        brand: Brand identifier
        geocode: Whether to geocode addresses (slow)
        skip_existing: Skip if store already exists

    Returns:
        Dict with import statistics
    """
    stats = {"imported": 0, "skipped": 0, "errors": 0, "geocoded": 0}

    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return stats

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                street = row.get('street', '').strip()
                city = row.get('city', '').strip()
                state = row.get('state', '').strip().upper()
                postal_code = row.get('postal_code', '').strip()

                # Skip empty rows
                if not city or not state:
                    stats["skipped"] += 1
                    continue

                # Check for existing store if skip_existing
                if skip_existing:
                    existing = db.query(Store).filter(
                        Store.brand == brand,
                        Store.street == street,
                        Store.city == city,
                        Store.state == state
                    ).first()

                    if existing:
                        stats["skipped"] += 1
                        continue

                # Create store record
                store = Store(
                    brand=brand,
                    street=street,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                )

                # First, try to read coordinates from CSV (pre-geocoded data)
                csv_lat = row.get('latitude', '').strip()
                csv_lng = row.get('longitude', '').strip()

                if csv_lat and csv_lng:
                    try:
                        store.latitude = float(csv_lat)
                        store.longitude = float(csv_lng)
                        # Set PostGIS geography point
                        store.location = func.ST_SetSRID(
                            func.ST_MakePoint(float(csv_lng), float(csv_lat)),
                            4326
                        )
                        stats["geocoded"] += 1
                    except ValueError:
                        pass  # Invalid coordinates, skip

                # Fall back to geocoding service if no coordinates and geocode=True
                elif geocode:
                    coords = geocoding_service.geocode_address(
                        street, city, state, postal_code
                    )
                    if coords:
                        store.latitude = coords[0]
                        store.longitude = coords[1]
                        # Set PostGIS geography point
                        store.location = func.ST_SetSRID(
                            func.ST_MakePoint(coords[1], coords[0]),
                            4326
                        )
                        stats["geocoded"] += 1

                db.add(store)
                stats["imported"] += 1

                # Commit in batches
                if stats["imported"] % 100 == 0:
                    db.commit()
                    logger.info(f"Imported {stats['imported']} stores from {csv_path.name}")

            except Exception as e:
                logger.error(f"Error importing row: {row}, error: {e}")
                stats["errors"] += 1

    # Final commit
    db.commit()
    logger.info(f"Import complete for {brand}: {stats}")

    return stats


def import_all_competitors(
    db: Session,
    data_dir: Path,
    geocode: bool = False
) -> dict:
    """
    Import all competitor CSV files from the data directory.

    Args:
        db: Database session
        data_dir: Path to directory containing CSV files
        geocode: Whether to geocode addresses

    Returns:
        Dict with stats per brand
    """
    all_stats = {}

    for filename, brand in BRAND_FILE_MAPPING.items():
        csv_path = data_dir / filename

        if csv_path.exists():
            logger.info(f"Importing {brand} from {filename}...")
            stats = import_csv_to_db(db, csv_path, brand, geocode=geocode)
            all_stats[brand] = stats
        else:
            logger.warning(f"File not found: {csv_path}")
            all_stats[brand] = {"error": "file not found"}

    return all_stats


def update_coordinates_from_geocoding(
    db: Session,
    batch_size: int = 100,
    brand: Optional[str] = None
) -> dict:
    """
    Update stores that are missing coordinates by geocoding.

    Args:
        db: Database session
        batch_size: Number of stores to process
        brand: Optional brand filter

    Returns:
        Stats dict
    """
    stats = {"processed": 0, "geocoded": 0, "failed": 0}

    query = db.query(Store).filter(Store.latitude.is_(None))
    if brand:
        query = query.filter(Store.brand == brand)

    stores = query.limit(batch_size).all()

    for store in stores:
        stats["processed"] += 1

        coords = geocoding_service.geocode_address(
            store.street, store.city, store.state, store.postal_code
        )

        if coords:
            store.latitude = coords[0]
            store.longitude = coords[1]
            store.location = func.ST_SetSRID(
                func.ST_MakePoint(coords[1], coords[0]),
                4326
            )
            stats["geocoded"] += 1
            logger.info(f"Geocoded: {store.city}, {store.state}")
        else:
            stats["failed"] += 1
            logger.warning(f"Failed to geocode: {store.full_address}")

        # Commit periodically
        if stats["processed"] % 10 == 0:
            db.commit()

    db.commit()
    return stats
