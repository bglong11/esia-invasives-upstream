import geopandas as gpd
import pandas as pd
import pytest

from _helpers import (
    make_synthetic_griis_rows,
    make_synthetic_occurrences_gdf,
)

from analyze import (
    IUCN_100_WORST,
    compute_establishment_breakdown,
    compute_summary_stats,
    compute_taxonomic_breakdown,
    compute_top_species,
    flag_griis_listed,
    flag_iucn_100,
)


def test_iucn_100_set_size():
    # Sanity: roughly the "100 worst" list (76 unique in source).
    assert 70 <= len(IUCN_100_WORST) <= 110
    assert "Lantana camara" in IUCN_100_WORST
    assert "Chromolaena odorata" in IUCN_100_WORST


def test_flag_iucn_100_adds_bool_column():
    gdf = make_synthetic_occurrences_gdf(n_per_species=3)
    out = flag_iucn_100(gdf)
    assert "iucn_100_flag" in out.columns
    assert out["iucn_100_flag"].dtype == bool
    # 2 of 3 synth species are in IUCN-100
    lantana = out.loc[out["species"] == "Lantana camara", "iucn_100_flag"]
    assert lantana.all()
    acrid = out.loc[out["species"] == "Acridotheres javanicus", "iucn_100_flag"]
    assert not acrid.any()


def test_flag_iucn_100_empty_input():
    empty = gpd.GeoDataFrame({"species": [], "geometry": []}, crs="EPSG:4326")
    out = flag_iucn_100(empty)
    assert "iucn_100_flag" in out.columns
    assert len(out) == 0


def test_flag_griis_listed():
    gdf = make_synthetic_occurrences_gdf(n_per_species=2)
    out = flag_griis_listed(gdf, griis_species=["Lantana camara", "Mikania micrantha"])
    assert "griis_listed" in out.columns
    assert out.loc[out["species"] == "Lantana camara", "griis_listed"].all()
    assert not out.loc[out["species"] == "Acridotheres javanicus", "griis_listed"].any()


def test_taxonomic_breakdown_per_kingdom_and_class():
    gdf = make_synthetic_occurrences_gdf(n_per_species=4)
    tb = compute_taxonomic_breakdown(gdf)
    assert "per_kingdom" in tb and "per_class" in tb
    # 2 plant species * 4 + 1 animal * 4 = 8 + 4
    assert tb["per_kingdom"].get("Plantae") == 8
    assert tb["per_kingdom"].get("Animalia") == 4


def test_taxonomic_breakdown_empty():
    empty = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")
    tb = compute_taxonomic_breakdown(empty)
    assert tb == {"per_kingdom": {}, "per_class": {}}


def test_establishment_breakdown_sums_to_total():
    gdf = make_synthetic_occurrences_gdf(n_per_species=5)
    eb = compute_establishment_breakdown(gdf)
    assert sum(eb.values()) == len(gdf)
    # 3 distinct establishmentMeans values across synth
    assert set(eb.keys()) == {"INVASIVE", "NATURALISED", "INTRODUCED"}


def test_top_species_orders_by_count_and_flags():
    gdf = make_synthetic_occurrences_gdf(n_per_species=5)
    gdf = flag_iucn_100(gdf)
    gdf = flag_griis_listed(gdf, griis_species=["Lantana camara"])
    top = compute_top_species(gdf, top_n=10)
    assert len(top) == 3
    # All synth species have 5 each — tie-broken by name; the contract is
    # that counts are present and flags are correct.
    by_name = {t["species"]: t for t in top}
    assert by_name["Lantana camara"]["iucn_100_flag"] is True
    assert by_name["Lantana camara"]["griis_listed"] is True
    assert by_name["Acridotheres javanicus"]["iucn_100_flag"] is False
    assert by_name["Acridotheres javanicus"]["griis_listed"] is False
    assert all(t["count"] == 5 for t in top)


def test_top_species_empty():
    empty = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")
    assert compute_top_species(empty) == []


def test_summary_stats_keys_and_counts():
    gdf = make_synthetic_occurrences_gdf(n_per_species=5)
    gdf = flag_iucn_100(gdf)
    griis_df = pd.DataFrame(make_synthetic_griis_rows())
    s = compute_summary_stats(gdf, griis_df, aoi_area_km2=42.5)
    assert s["gbif_occurrence_count"] == 15
    assert s["gbif_species_count"] == 3
    assert s["griis_species_count"] == 2
    assert s["iucn_100_count"] == 10  # Lantana + Chromolaena = 2 * 5
    assert s["aoi_area_km2"] == 42.5


def test_summary_stats_empty_inputs():
    empty = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")
    s = compute_summary_stats(empty, pd.DataFrame(), 10.0)
    assert s["gbif_occurrence_count"] == 0
    assert s["gbif_species_count"] == 0
    assert s["griis_species_count"] == 0
    assert s["iucn_100_count"] == 0
