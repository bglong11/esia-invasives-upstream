from pathlib import Path

from _helpers import write_aoi_geojson

from utils import bbox_to_wkt, compute_aoi_hash, point_radius_to_wkt, polygon_to_wkt
from shapely import wkt as shapely_wkt
from shapely.geometry import box


def test_point_radius_to_wkt_centred_polygon():
    w = point_radius_to_wkt(0.0, 0.0, radius_km=10.0)
    poly = shapely_wkt.loads(w)
    minx, miny, maxx, maxy = poly.bounds
    # At equator, 10 km ~ 0.0899 deg in both lat and lon
    assert abs(maxx - minx - 2 * 0.0899) < 0.005
    assert abs(maxy - miny - 2 * 0.0899) < 0.005


def test_point_radius_to_wkt_latitude_correction():
    """At higher latitudes, longitudinal span should widen."""
    w_eq = point_radius_to_wkt(0.0, 0.0, radius_km=10.0)
    w_hi = point_radius_to_wkt(60.0, 0.0, radius_km=10.0)
    span_eq = shapely_wkt.loads(w_eq).bounds[2] - shapely_wkt.loads(w_eq).bounds[0]
    span_hi = shapely_wkt.loads(w_hi).bounds[2] - shapely_wkt.loads(w_hi).bounds[0]
    assert span_hi > span_eq * 1.5


def test_bbox_to_wkt_roundtrip():
    w = bbox_to_wkt(120.0, -9.0, 121.0, -8.0)
    poly = shapely_wkt.loads(w)
    assert poly.bounds == (120.0, -9.0, 121.0, -8.0)


def test_polygon_to_wkt_roundtrip():
    poly = box(120.0, -9.0, 121.0, -8.0)
    w = polygon_to_wkt(poly)
    assert shapely_wkt.loads(w).equals(poly)


def test_compute_aoi_hash_deterministic(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    h1 = compute_aoi_hash(aoi)
    h2 = compute_aoi_hash(aoi)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)
