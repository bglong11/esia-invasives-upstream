"""Shared utilities: AOI WKT helpers, hashing.

Lifted from ``~/github-ubuntu/esia-invasives/query_invasives.py``: the
``point_radius_to_wkt`` / ``bbox_to_wkt`` helpers are preserved verbatim.
Presentation-layer helpers (env parsing, CLI dispatch) are dropped.
"""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

from shapely.geometry import Polygon


DEFAULT_RADIUS_KM = 10.0
EARTH_RADIUS_KM = 6371.0


def point_radius_to_wkt(lat: float, lon: float, radius_km: float = DEFAULT_RADIUS_KM) -> str:
    """Generate a metrically-accurate square WKT polygon around a point.

    Side length = 2 * radius_km; latitude-corrected longitudinal offset.
    Counter-clockwise winding (GBIF-compatible).
    """
    lat_offset = radius_km / 111.32
    lon_offset = radius_km / (111.32 * math.cos(math.radians(lat)))
    min_lon = round(lon - lon_offset, 6)
    max_lon = round(lon + lon_offset, 6)
    min_lat = round(lat - lat_offset, 6)
    max_lat = round(lat + lat_offset, 6)
    return (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


def bbox_to_wkt(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    """Convert a bounding box to a WKT polygon (counter-clockwise)."""
    return (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


def polygon_to_wkt(poly: Polygon) -> str:
    """Shapely polygon → WKT string (re-uses Shapely's WKT writer)."""
    return poly.wkt


def compute_aoi_hash(aoi_path: str | os.PathLike) -> str:
    """SHA-256 of the AOI GeoJSON bytes — for provenance."""
    with open(aoi_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
