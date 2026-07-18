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


def test_truncated_gbif_page_raises_rather_than_silently_under_reporting():
    """GBIF reporting more records than we retrieved must not pass silently.

    The paging loop is bounded by ``max_records``. Hitting that bound looked
    identical to a complete download, so an AOI with more occurrences than the
    cap silently under-reported invasive species. GBIF's own ``count`` is the
    available oracle — a total derived by the server, not by our paging.
    """
    records = make_synthetic_occurrence_records(100)  # 3 species x 100 = 300 = GBIF_LIMIT
    with requests_mock.Mocker() as m:
        # Server insists there are 1000 matches; every page says "more to come".
        page = mock_occurrence_page(records, end=False)
        page["count"] = 1000
        m.get(f"{GBIF_API}/occurrence/search", json=page)

        dl = GBIFDownloader()
        with pytest.raises(RuntimeError, match="1000"):
            dl.query_occurrences(WKT, establishment_means=["INTRODUCED"],
                                 max_records=600)


def test_allow_partial_downgrades_truncation_to_a_warning(caplog):
    """The escape hatch warns and proceeds — it does not invent a policy."""
    records = make_synthetic_occurrence_records(100)  # 3 species x 100 = 300 = GBIF_LIMIT
    with requests_mock.Mocker() as m:
        page = mock_occurrence_page(records, end=False)
        page["count"] = 1000
        m.get(f"{GBIF_API}/occurrence/search", json=page)

        dl = GBIFDownloader()
        gdf = dl.query_occurrences(WKT, establishment_means=["INTRODUCED"],
                                   max_records=600, allow_partial=True)
    assert not gdf.empty
    assert any("1000" in r.message for r in caplog.records)


def test_complete_download_does_not_raise():
    """A page that ends cleanly with count == retrieved stays silent."""
    records = make_synthetic_occurrence_records(1)
    with requests_mock.Mocker() as m:
        m.get(f"{GBIF_API}/occurrence/search",
              json=mock_occurrence_page(records, end=True))
        dl = GBIFDownloader()
        gdf = dl.query_occurrences(WKT, establishment_means=["INTRODUCED"])
    assert len(gdf) == len(records)


def test_paging_never_exceeds_gbif_offset_ceiling(monkeypatch):
    """GBIF rejects offset + limit > GBIF_MAX_OFFSET.

    The final page must be shortened to land exactly on the ceiling instead of
    overshooting into an HTTP error. Ceiling is monkeypatched small so the
    boundary is exercised without paging 100k records.
    """
    import download as dl_mod
    monkeypatch.setattr(dl_mod, "GBIF_MAX_OFFSET", 500)

    records = make_synthetic_occurrence_records(100)  # 300 per page
    with requests_mock.Mocker() as m:
        page = mock_occurrence_page(records, end=False)
        page["count"] = 10_000
        m.get(f"{GBIF_API}/occurrence/search", json=page)

        dl = GBIFDownloader()
        with pytest.raises(RuntimeError):
            dl.query_occurrences(WKT, establishment_means=["INTRODUCED"],
                                 max_records=100_000)

        pairs = [(int(r.qs["offset"][0]), int(r.qs["limit"][0]))
                 for r in m.request_history]
        # Second page is shortened to land exactly on the ceiling.
        assert pairs == [(0, 300), (300, 200)], pairs


def test_page_size_respects_a_cap_smaller_than_one_page():
    """max_records=1 must request 1 record, not a full 300-row page."""
    records = make_synthetic_occurrence_records(1)
    with requests_mock.Mocker() as m:
        page = mock_occurrence_page(records, end=True)
        page["count"] = 1
        m.get(f"{GBIF_API}/occurrence/search", json=page)

        dl = GBIFDownloader()
        dl.query_occurrences(WKT, establishment_means=["INTRODUCED"],
                             max_records=1)
        assert int(m.request_history[0].qs["limit"][0]) == 1


def test_missing_count_fails_closed():
    """With no oracle we cannot claim completeness, so refuse to."""
    records = make_synthetic_occurrence_records(1)
    with requests_mock.Mocker() as m:
        page = mock_occurrence_page(records, end=True)
        del page["count"]
        m.get(f"{GBIF_API}/occurrence/search", json=page)

        dl = GBIFDownloader()
        with pytest.raises(RuntimeError, match="count"):
            dl.query_occurrences(WKT, establishment_means=["INTRODUCED"])


def test_counts_do_not_leak_between_establishment_means():
    """Each filter carries its own count; one must not satisfy another."""
    records = make_synthetic_occurrence_records(1)

    def _by_filter(request, context):
        est = request.qs["establishmentmeans"][0].upper()
        page = mock_occurrence_page(records, end=True)
        # INTRODUCED is complete; NATURALISED claims far more than it returns.
        page["count"] = len(records) if est == "INTRODUCED" else 9_999
        return page

    with requests_mock.Mocker() as m:
        m.get(f"{GBIF_API}/occurrence/search", json=_by_filter)
        dl = GBIFDownloader()
        with pytest.raises(RuntimeError, match="9999|NATURALISED"):
            dl.query_occurrences(WKT,
                                 establishment_means=["INTRODUCED", "NATURALISED"])


def test_count_of_true_is_not_a_usable_oracle():
    """bool subclasses int — a malformed count must not satisfy the check."""
    records = make_synthetic_occurrence_records(1)
    with requests_mock.Mocker() as m:
        page = mock_occurrence_page(records, end=True)
        page["count"] = True
        m.get(f"{GBIF_API}/occurrence/search", json=page)
        dl = GBIFDownloader()
        with pytest.raises(RuntimeError, match="count"):
            dl.query_occurrences(WKT, establishment_means=["INTRODUCED"])
