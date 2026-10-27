"""Geo yordamchilari (PostGIS kerak emas). Davomat geofence (F6) ham shu yerdan foydalanadi."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Ikki nuqta orasidagi masofa (metr), katta doira bo'yicha."""
    p1, p2 = radians(lat1), radians(lat2)
    dphi = p2 - p1
    dlmb = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def within_radius(
    lat: float, lng: float, center_lat: float, center_lng: float, radius_m: float
) -> bool:
    return haversine_m(lat, lng, center_lat, center_lng) <= radius_m


def valid_coordinates(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    return -90 <= lat <= 90 and -180 <= lng <= 180
