"""Download tests — GBIF REST mocked via requests-mock."""

from __future__ import annotations

import pytest
import requests_mock

from _helpers import (
    make_synthetic_griis_rows,
    make_synthetic_occurrence_records,
    mock_dataset_search_griis,
    mock_occurrence_page,
    mock_species_search_page,
)

from download import GBIF_API, GBIF_COLS, GBIFDownloader


WKT = "POLYGON((121.04 -8.68, 121.10 -8.68, 121.10 -8.62, 121.04 -8.62, 121.04 -8.68))"


def test_query_occurrences_returns_points_gdf():
    records = make_synthetic_occurrence_records(n_per_species=5)
    # Return all records under the first establishmentMeans, none under the others.
    with requests_mock.Mocker() as m:
        m.get(
            f"{GBIF_API}/occurrence/search",
            json=mock_occurrence_page(records, end=True),
        )
        gdf = GBIFDownloader().query_occurrences(WKT, max_records=1000)

    assert not gdf.empty
    # 3 species * 5 records = 15 unique on (species, lat, lon)
    assert len(gdf) == 15
    assert gdf.crs.to_epsg() == 4326
    # Every required column present
    for col in ("species", "kingdom", "decimalLatitude", "establishmentMeans"):
        assert col in gdf.columns
    # geometry built from coords
    assert all(p.geom_type == "Point" for p in gdf.geometry)


def test_query_occurrences_empty_returns_schema_valid_gdf():
    with requests_mock.Mocker() as m:
        m.get(
            f"{GBIF_API}/occurrence/search",
            json=mock_occurrence_page([], end=True),
        )
        gdf = GBIFDownloader().query_occurrences(WKT)
    assert gdf.empty
    # Schema columns are still present
    for col in GBIF_COLS:
        assert col in gdf.columns


def test_query_occurrences_deduplicates_on_species_latlon():
    """Duplicate occurrence rows (same species + coord) should be collapsed."""
    rec = {
        "species": "Lantana camara",
        "scientificName": "Lantana camara L.",
        "kingdom": "Plantae", "class": "Magnoliopsida", "family": "Verbenaceae",
        "decimalLatitude": -8.65, "decimalLongitude": 121.07,
        "establishmentMeans": "INVASIVE",
    }
    records = [dict(rec) for _ in range(3)]
    with requests_mock.Mocker() as m:
        m.get(f"{GBIF_API}/occurrence/search",
              json=mock_occurrence_page(records, end=True))
        gdf = GBIFDownloader().query_occurrences(WKT)
    assert len(gdf) == 1


def test_fetch_griis_checklist_returns_dataframe():
    griis_rows = make_synthetic_griis_rows()
    with requests_mock.Mocker() as m:
        m.get(f"{GBIF_API}/dataset/search", json=mock_dataset_search_griis("Indonesia"))
        m.get(f"{GBIF_API}/species/search", json=mock_species_search_page(griis_rows, end=True))
        df = GBIFDownloader().fetch_griis_checklist("Indonesia")
    assert len(df) == len(griis_rows)
    assert "canonicalName" in df.columns
    assert set(df["canonicalName"]) == {"Lantana camara", "Mikania micrantha"}


def test_fetch_griis_checklist_no_dataset_returns_empty():
    with requests_mock.Mocker() as m:
        m.get(f"{GBIF_API}/dataset/search", json={"results": []})
        df = GBIFDownloader().fetch_griis_checklist("Atlantis")
    assert df.empty


def test_fetch_griis_checklist_no_species_returns_empty():
    with requests_mock.Mocker() as m:
        m.get(f"{GBIF_API}/dataset/search", json=mock_dataset_search_griis("Indonesia"))
        m.get(f"{GBIF_API}/species/search", json=mock_species_search_page([], end=True))
        df = GBIFDownloader().fetch_griis_checklist("Indonesia")
    assert df.empty


def test_gbif_api_pinned():
    """Pin the base URL — accidental drift is a one-way data shift."""
    assert GBIF_API == "https://api.gbif.org/v1"
