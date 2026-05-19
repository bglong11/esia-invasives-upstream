"""AOI loading + WKT/point/bbox → shapely + GeoDataFrame.

Supports four AOI input forms:
    * GeoJSON file path
    * Shapefile path
    * Inline GeoJSON dict
    * WKT string
    * Point + radius (km) — convenience for quick CLI-style runs.

The returned GeoDataFrame is always in EPSG:4326.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import geopandas as gpd
from shapely.geometry import Polygon, shape

from utils import point_radius_to_wkt


def load_aoi_gdf(aoi_path: str | os.PathLike) -> gpd.GeoDataFrame:
    """Load AOI GeoJSON / shapefile as a GeoDataFrame in EPSG:4326."""
    gdf = gpd.read_file(aoi_path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def aoi_to_polygon(aoi_gdf: gpd.GeoDataFrame) -> Polygon:
    """Dissolve an AOI GeoDataFrame to a single Polygon (in EPSG:4326)."""
    if aoi_gdf.empty:
        raise ValueError("AOI GeoDataFrame is empty")
    geom = aoi_gdf.unary_union
    if geom.geom_type == "Polygon":
        return geom
    if geom.geom_type == "MultiPolygon":
        # GBIF accepts a single polygon — take the convex hull of the multi.
        return geom.convex_hull
    raise ValueError(f"Unsupported AOI geom type: {geom.geom_type}")


def aoi_area_sq_km(aoi_gdf: gpd.GeoDataFrame) -> float:
    """Total AOI area in km², via UTM reprojection."""
    if aoi_gdf.empty:
        return 0.0
    utm = aoi_gdf.estimate_utm_crs()
    return float(aoi_gdf.to_crs(utm).geometry.area.sum() / 1e6)


def resolve_aoi(
    aoi_geojson: Optional[str | os.PathLike] = None,
    aoi_shapefile: Optional[str | os.PathLike] = None,
    aoi_geojson_inline: Optional[dict] = None,
    wkt: Optional[str] = None,
    point: Optional[tuple[float, float]] = None,
    radius_km: float = 10.0,
) -> gpd.GeoDataFrame:
    """Resolve any of the supported AOI inputs to a GeoDataFrame (EPSG:4326)."""
    if aoi_geojson is not None:
        return load_aoi_gdf(aoi_geojson)
    if aoi_shapefile is not None:
        return load_aoi_gdf(aoi_shapefile)
    if aoi_geojson_inline is not None:
        gj = aoi_geojson_inline
        if gj.get("type") == "FeatureCollection":
            feats = gj["features"]
        elif gj.get("type") == "Feature":
            feats = [gj]
        else:
            feats = [{"type": "Feature", "geometry": gj, "properties": {}}]
        return gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    if wkt is not None:
        from shapely import wkt as _wkt
        geom = _wkt.loads(wkt)
        return gpd.GeoDataFrame({"geometry": [geom]}, crs="EPSG:4326")
    if point is not None:
        lat, lon = point
        from shapely import wkt as _wkt
        geom = _wkt.loads(point_radius_to_wkt(lat, lon, radius_km))
        return gpd.GeoDataFrame({"geometry": [geom]}, crs="EPSG:4326")
    raise ValueError("resolve_aoi: must provide one of aoi_geojson, aoi_shapefile, "
                     "aoi_geojson_inline, wkt, point")
