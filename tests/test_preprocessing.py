from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from _helpers import write_aoi_geojson

from preprocessing import (
    aoi_area_sq_km,
    aoi_to_polygon,
    load_aoi_gdf,
    resolve_aoi,
)


def test_load_aoi_gdf_normalises_to_wgs84(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    gdf = load_aoi_gdf(aoi)
    assert gdf.crs.to_epsg() == 4326
    assert len(gdf) == 1


def test_aoi_to_polygon_returns_single_polygon(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    poly = aoi_to_polygon(load_aoi_gdf(aoi))
    assert isinstance(poly, Polygon)


def test_aoi_area_sq_km_positive(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    km2 = aoi_area_sq_km(load_aoi_gdf(aoi))
    # ~0.06° square at -8.65° lat ≈ ~43 km²
    assert 20 < km2 < 80


def test_aoi_area_sq_km_empty_is_zero():
    empty = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")
    assert aoi_area_sq_km(empty) == 0.0


def test_resolve_aoi_from_point_radius():
    gdf = resolve_aoi(point=(-8.65, 121.07), radius_km=10.0)
    assert gdf.crs.to_epsg() == 4326
    assert len(gdf) == 1
    assert isinstance(gdf.geometry.iloc[0], Polygon)


def test_resolve_aoi_from_wkt():
    wkt = "POLYGON((120 -9, 121 -9, 121 -8, 120 -8, 120 -9))"
    gdf = resolve_aoi(wkt=wkt)
    assert len(gdf) == 1
    assert gdf.geometry.iloc[0].area > 0


def test_resolve_aoi_from_geojson_inline():
    gj = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[120, -9], [121, -9], [121, -8], [120, -8], [120, -9]]],
        },
        "properties": {},
    }
    gdf = resolve_aoi(aoi_geojson_inline=gj)
    assert len(gdf) == 1


def test_resolve_aoi_requires_some_input():
    with pytest.raises(ValueError):
        resolve_aoi()
