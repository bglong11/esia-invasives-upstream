"""Fixtures: synthetic AOI + synthetic GBIF/GRIIS responses."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box


# Ulumbu-ish lat/lon (Flores, Indonesia)
AOI_LON_MIN, AOI_LON_MAX = 121.04, 121.10
AOI_LAT_MIN, AOI_LAT_MAX = -8.68, -8.62


def make_aoi_polygon():
    return box(AOI_LON_MIN, AOI_LAT_MIN, AOI_LON_MAX, AOI_LAT_MAX)


def write_aoi_geojson(path: Path) -> Path:
    feat = {
        "type": "Feature",
        "geometry": json.loads(
            gpd.GeoSeries([make_aoi_polygon()], crs="EPSG:4326").to_json()
        )["features"][0]["geometry"],
        "properties": {},
    }
    fc = {"type": "FeatureCollection", "features": [feat]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fc))
    return path


# Three species: one IUCN-100 worst, one GRIIS-only candidate, one neutral.
SYNTH_SPECIES = [
    {
        "species": "Lantana camara",       # IUCN-100 worst
        "scientificName": "Lantana camara L.",
        "kingdom": "Plantae", "phylum": "Tracheophyta", "class": "Magnoliopsida",
        "order": "Lamiales", "family": "Verbenaceae", "genus": "Lantana",
        "establishmentMeans": "INVASIVE",
        "degreeOfEstablishment": "established",
    },
    {
        "species": "Chromolaena odorata",  # IUCN-100 worst
        "scientificName": "Chromolaena odorata (L.) R.M.King & H.Rob.",
        "kingdom": "Plantae", "phylum": "Tracheophyta", "class": "Magnoliopsida",
        "order": "Asterales", "family": "Asteraceae", "genus": "Chromolaena",
        "establishmentMeans": "NATURALISED",
        "degreeOfEstablishment": "established",
    },
    {
        "species": "Acridotheres javanicus",  # NOT in IUCN-100
        "scientificName": "Acridotheres javanicus Cabanis, 1851",
        "kingdom": "Animalia", "phylum": "Chordata", "class": "Aves",
        "order": "Passeriformes", "family": "Sturnidae", "genus": "Acridotheres",
        "establishmentMeans": "INTRODUCED",
        "degreeOfEstablishment": "established",
    },
]


def make_synthetic_occurrence_records(n_per_species: int = 5) -> list[dict]:
    """A list of GBIF-shaped occurrence dicts inside the AOI."""
    import random
    random.seed(7)
    records = []
    for sp in SYNTH_SPECIES:
        for i in range(n_per_species):
            lon = random.uniform(AOI_LON_MIN + 0.005, AOI_LON_MAX - 0.005)
            lat = random.uniform(AOI_LAT_MIN + 0.005, AOI_LAT_MAX - 0.005)
            records.append({
                **sp,
                "decimalLatitude": lat,
                "decimalLongitude": lon,
                "eventDate": "2024-01-15",
                "basisOfRecord": "HUMAN_OBSERVATION",
                "datasetName": "synthetic",
                "occurrenceID": f"synthetic-{sp['species'].replace(' ', '_')}-{i}",
            })
    return records


def make_synthetic_occurrences_gdf(n_per_species: int = 5) -> gpd.GeoDataFrame:
    records = make_synthetic_occurrence_records(n_per_species)
    df = pd.DataFrame(records)
    geom = [Point(r["decimalLongitude"], r["decimalLatitude"]) for r in records]
    return gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")


def make_synthetic_griis_rows() -> list[dict]:
    return [
        {
            "key": 1, "scientificName": "Lantana camara L.", "canonicalName": "Lantana camara",
            "kingdom": "Plantae", "phylum": "Tracheophyta", "class": "Magnoliopsida",
            "order": "Lamiales", "family": "Verbenaceae", "genus": "Lantana",
            "taxonomicStatus": "ACCEPTED", "rank": "SPECIES",
            "establishmentMeans": "INVASIVE", "degreeOfEstablishment": "established",
        },
        {
            "key": 2, "scientificName": "Mikania micrantha Kunth", "canonicalName": "Mikania micrantha",
            "kingdom": "Plantae", "phylum": "Tracheophyta", "class": "Magnoliopsida",
            "order": "Asterales", "family": "Asteraceae", "genus": "Mikania",
            "taxonomicStatus": "ACCEPTED", "rank": "SPECIES",
            "establishmentMeans": "INVASIVE", "degreeOfEstablishment": "established",
        },
    ]


# ---- mock GBIF JSON responses (shape matches https://api.gbif.org/v1) ----

def mock_occurrence_page(records: list[dict], offset: int = 0, end: bool = True) -> dict:
    return {
        "offset": offset,
        "limit": 300,
        "endOfRecords": end,
        "count": len(records),
        "results": records,
    }


def mock_dataset_search_griis(country: str = "Indonesia") -> dict:
    return {
        "results": [
            {"key": "griis-uuid-1234",
             "title": f"GRIIS - Global Register of Introduced and Invasive Species - {country}"},
        ]
    }


def mock_species_search_page(records: list[dict], end: bool = True) -> dict:
    return {
        "offset": 0,
        "limit": 300,
        "endOfRecords": end,
        "results": records,
    }
