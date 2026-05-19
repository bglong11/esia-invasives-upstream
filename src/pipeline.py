"""Invasives pipeline orchestrator.

Thin orchestration over the GBIF + GRIIS REST queries lifted from
``esia-invasives/query_invasives.py`` (Phases 1 + 2 only). Loads an AOI,
queries GBIF occurrences (filtered by establishmentMeans), fetches the GRIIS
country checklist, flags IUCN-100 + GRIIS-listed species, computes
breakdowns + top-species, writes the flat bundle.

NO LLM. NO Tavily. NO matplotlib. Bundle assembly is the consuming
Baseline App's job.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

import geopandas as gpd

from analyze import (
    compute_establishment_breakdown,
    compute_summary_stats,
    compute_taxonomic_breakdown,
    compute_top_species,
    flag_griis_listed,
    flag_iucn_100,
)
from download import GBIFDownloader, _empty_occurrences_gdf
from manifest import write_manifest
from preprocessing import aoi_area_sq_km, aoi_to_polygon, load_aoi_gdf
from utils import compute_aoi_hash, polygon_to_wkt


log = logging.getLogger(__name__)


def _bundle_dir(output_root: Path, project: str, extraction_year: int) -> Path:
    d = Path(output_root) / project / "invasives" / str(extraction_year)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _freeze_aoi(aoi_path: Path, bundle_dir: Path) -> Path:
    dst = bundle_dir / "aoi.geojson"
    shutil.copyfile(aoi_path, dst)
    return dst


def _griis_species_names(griis_df) -> list[str]:
    if griis_df is None or griis_df.empty:
        return []
    col = "canonicalName" if "canonicalName" in griis_df.columns else "scientificName"
    if col not in griis_df.columns:
        return []
    return [s for s in griis_df[col].dropna().astype(str).tolist() if s]


def run(
    aoi_geojson: str | Path,
    project: str,
    country_name: str,
    extraction_year: int,
    output_root: str | Path = "data/outputs",
    downloader: Optional[GBIFDownloader] = None,
    max_records: int = 100_000,
) -> Path:
    """Run the invasives pipeline end-to-end.

    Args:
        aoi_geojson: Path to a GeoJSON AOI (Feature / FeatureCollection of Polygons).
        project: Project slug.
        country_name: Country name for GRIIS checklist lookup (e.g. ``"Indonesia"``).
        extraction_year: Provenance label for the run.
        output_root: Root under which ``<project>/invasives/<year>/`` is created.
        downloader: Optional ``GBIFDownloader`` (defaults to a fresh instance).
        max_records: Cap on GBIF occurrence rows per establishmentMeans class.

    Returns:
        Path to the written bundle directory.
    """
    aoi_path = Path(aoi_geojson)
    bundle = _bundle_dir(Path(output_root), project, extraction_year)
    log.info("invasives pipeline starting: project=%s year=%s bundle=%s",
             project, extraction_year, bundle)

    aoi_gdf = load_aoi_gdf(aoi_path)
    aoi_km2 = aoi_area_sq_km(aoi_gdf)
    wkt = polygon_to_wkt(aoi_to_polygon(aoi_gdf))

    dl = downloader or GBIFDownloader()

    gdf = dl.query_occurrences(wkt, max_records=max_records)
    griis_df = dl.fetch_griis_checklist(country_name) if country_name else None

    griis_names = _griis_species_names(griis_df)
    gdf = flag_iucn_100(gdf)
    gdf = flag_griis_listed(gdf, griis_names)

    # ---- artefacts ----
    gpkg_path = bundle / "species_occurrences.gpkg"
    if gdf.empty:
        # Write an empty but schema-valid GPKG by writing a single-row stub + deleting.
        # geopandas refuses to write a truly empty layer in some drivers, so we
        # round-trip an empty schema by writing a placeholder and then truncating.
        stub = _empty_occurrences_gdf()
        # Add the two flag columns so the schema is complete.
        stub = flag_iucn_100(stub)
        stub = flag_griis_listed(stub, [])
        # GeoPandas can write an empty GeoDataFrame if a geometry column exists.
        stub.to_file(gpkg_path, driver="GPKG")
    else:
        gdf.to_file(gpkg_path, driver="GPKG")

    griis_csv_path = bundle / "griis_checklist.csv"
    if griis_df is not None and not griis_df.empty:
        griis_df.to_csv(griis_csv_path, index=False)
    else:
        # Schema-valid empty CSV (header only).
        from download import GRIIS_KEEP_COLS
        import pandas as pd  # noqa: WPS433 — local import keeps top tidy
        pd.DataFrame(columns=list(GRIIS_KEEP_COLS)).to_csv(griis_csv_path, index=False)

    stats_payload = {
        "summary": compute_summary_stats(gdf, griis_df, aoi_km2),
        "taxonomic_breakdown": compute_taxonomic_breakdown(gdf),
        "establishment_breakdown": compute_establishment_breakdown(gdf),
        "top_species": compute_top_species(gdf, top_n=20),
        "_provenance": {
            "aoi_sha256": compute_aoi_hash(aoi_path),
            "dataset": "GBIF + GRIIS",
            "extraction_year": int(extraction_year),
            "country_name": country_name,
        },
    }
    stats_path = bundle / "statistics.json"
    stats_path.write_text(json.dumps(stats_payload, indent=2, sort_keys=True))

    aoi_frozen = _freeze_aoi(aoi_path, bundle)

    artefacts = {
        "species_occurrences_gpkg": gpkg_path,
        "griis_checklist_csv": griis_csv_path,
        "statistics_json": stats_path,
        "aoi_geojson": aoi_frozen,
    }
    write_manifest(bundle, project=project, extraction_year=extraction_year, artefacts=artefacts)

    log.info("invasives pipeline done: %s", bundle)
    return bundle
