"""End-to-end pipeline integration test — GBIF REST mocked via requests-mock."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests_mock

from _helpers import (
    make_synthetic_griis_rows,
    make_synthetic_occurrence_records,
    mock_dataset_search_griis,
    mock_occurrence_page,
    mock_species_search_page,
    write_aoi_geojson,
)

import pipeline as pipeline_mod
from download import GBIF_API


def _install_full_mock(m: requests_mock.Mocker, occ_records: list[dict], griis_rows: list[dict]):
    m.get(f"{GBIF_API}/occurrence/search",
          json=mock_occurrence_page(occ_records, end=True))
    m.get(f"{GBIF_API}/dataset/search",
          json=mock_dataset_search_griis("Indonesia"))
    m.get(f"{GBIF_API}/species/search",
          json=mock_species_search_page(griis_rows, end=True))


def test_pipeline_writes_full_bundle(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    occ = make_synthetic_occurrence_records(n_per_species=5)
    griis = make_synthetic_griis_rows()

    with requests_mock.Mocker() as m:
        _install_full_mock(m, occ, griis)
        bundle = pipeline_mod.run(
            aoi_geojson=aoi,
            project="ulumbu",
            country_name="Indonesia",
            extraction_year=2024,
            output_root=tmp_path / "out",
        )

    assert bundle == tmp_path / "out" / "ulumbu" / "invasives" / "2024"
    assert (bundle / "species_occurrences.gpkg").exists()
    assert (bundle / "griis_checklist.csv").exists()
    assert (bundle / "statistics.json").exists()
    assert (bundle / "aoi.geojson").exists()
    assert (bundle / "manifest.json").exists()


def test_pipeline_statistics_json_schema(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    occ = make_synthetic_occurrence_records(n_per_species=4)
    griis = make_synthetic_griis_rows()

    with requests_mock.Mocker() as m:
        _install_full_mock(m, occ, griis)
        bundle = pipeline_mod.run(
            aoi_geojson=aoi, project="ulumbu", country_name="Indonesia",
            extraction_year=2024, output_root=tmp_path / "out",
        )

    stats = json.loads((bundle / "statistics.json").read_text())

    for k in ("summary", "taxonomic_breakdown", "establishment_breakdown",
              "top_species", "_provenance"):
        assert k in stats, f"missing key: {k}"

    assert stats["summary"]["gbif_occurrence_count"] == 12  # 3 * 4
    assert stats["summary"]["gbif_species_count"] == 3
    assert stats["summary"]["griis_species_count"] == 2
    assert stats["summary"]["iucn_100_count"] == 8  # Lantana + Chromolaena = 2 * 4

    assert stats["_provenance"]["country_name"] == "Indonesia"
    assert stats["_provenance"]["extraction_year"] == 2024
    assert len(stats["_provenance"]["aoi_sha256"]) == 64
    assert stats["_provenance"]["dataset"] == "GBIF + GRIIS"


def test_pipeline_gpkg_contains_flags(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    occ = make_synthetic_occurrence_records(n_per_species=3)
    griis = make_synthetic_griis_rows()

    with requests_mock.Mocker() as m:
        _install_full_mock(m, occ, griis)
        bundle = pipeline_mod.run(
            aoi_geojson=aoi, project="ulumbu", country_name="Indonesia",
            extraction_year=2024, output_root=tmp_path / "out",
        )

    on_disk = gpd.read_file(bundle / "species_occurrences.gpkg")
    assert "iucn_100_flag" in on_disk.columns
    assert "griis_listed" in on_disk.columns
    assert "species" in on_disk.columns
    # 2 of 3 synth species are IUCN-100 → 6 of 9 occurrences flagged
    assert int(on_disk["iucn_100_flag"].sum()) == 6


def test_pipeline_manifest_lists_all_artefacts(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    occ = make_synthetic_occurrence_records(n_per_species=2)
    griis = make_synthetic_griis_rows()

    with requests_mock.Mocker() as m:
        _install_full_mock(m, occ, griis)
        bundle = pipeline_mod.run(
            aoi_geojson=aoi, project="ulumbu", country_name="Indonesia",
            extraction_year=2024, output_root=tmp_path / "out",
        )

    m_json = json.loads((bundle / "manifest.json").read_text())
    kinds = {e["kind"] for e in m_json["artefacts"]}
    assert kinds == {
        "species_occurrences_gpkg",
        "griis_checklist_csv",
        "statistics_json",
        "aoi_geojson",
    }
    assert m_json["discipline"] == "invasives_baseline"
    assert m_json["project"] == "ulumbu"
    assert m_json["extraction_year"] == 2024


def test_pipeline_frozen_aoi_matches_input(tmp_path: Path):
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    with requests_mock.Mocker() as m:
        _install_full_mock(m, [], [])
        bundle = pipeline_mod.run(
            aoi_geojson=aoi, project="ulumbu", country_name="Indonesia",
            extraction_year=2024, output_root=tmp_path / "out",
        )
    assert (bundle / "aoi.geojson").read_bytes() == aoi.read_bytes()


def test_pipeline_empty_gbif_writes_schema_valid_bundle(tmp_path: Path):
    """Zero occurrences + no GRIIS dataset — bundle must still be schema-valid."""
    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    with requests_mock.Mocker() as m:
        m.get(f"{GBIF_API}/occurrence/search",
              json=mock_occurrence_page([], end=True))
        m.get(f"{GBIF_API}/dataset/search", json={"results": []})
        bundle = pipeline_mod.run(
            aoi_geojson=aoi, project="ulumbu", country_name="Atlantis",
            extraction_year=2024, output_root=tmp_path / "out",
        )

    stats = json.loads((bundle / "statistics.json").read_text())
    assert stats["summary"]["gbif_occurrence_count"] == 0
    assert stats["summary"]["griis_species_count"] == 0
    # All artefacts present
    for fn in ("species_occurrences.gpkg", "griis_checklist.csv",
               "statistics.json", "aoi.geojson", "manifest.json"):
        assert (bundle / fn).exists()
    # CSV has header but no data
    csv_rows = (bundle / "griis_checklist.csv").read_text().strip().splitlines()
    assert len(csv_rows) == 1  # header only
