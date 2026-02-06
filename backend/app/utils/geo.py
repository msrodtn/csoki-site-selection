"""Shared geospatial utilities."""

from math import radians, cos, sin, asin, sqrt


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great circle distance in miles between two points on earth.

    Args:
        lon1: Longitude of point 1 (decimal degrees)
        lat1: Latitude of point 1 (decimal degrees)
        lon2: Longitude of point 2 (decimal degrees)
        lat2: Latitude of point 2 (decimal degrees)

    Returns:
        Distance in miles.
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return c * 3956  # Earth radius in miles
