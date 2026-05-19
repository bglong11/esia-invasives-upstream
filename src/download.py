"""GBIF REST downloader.

Lifted from ``~/github-ubuntu/esia-invasives/query_invasives.py``:
``download_invasive_occurrences`` (Phase 1) and ``get_griis_checklist``
(Phase 2). Logging via module logger; behaviour otherwise preserved.

NO LLM. NO Tavily. NO per-species GBIF taxon-match enrichment beyond what is
needed to materialise the GRIIS country checklist — Phase 3+ stays out.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point


log = logging.getLogger(__name__)

GBIF_API = "https://api.gbif.org/v1"
GBIF_LIMIT = 300
REQUEST_TIMEOUT = 30
MAX_GRIIS_SPECIES = 5_000
ESTABLISHMENT_MEANS: tuple[str, ...] = ("INVASIVE", "INTRODUCED", "NATURALISED")

GBIF_COLS = (
    "species", "scientificName", "kingdom", "phylum", "class", "order",
    "family", "genus", "decimalLatitude", "decimalLongitude", "eventDate",
    "basisOfRecord", "establishmentMeans", "degreeOfEstablishment",
    "datasetName", "occurrenceID",
)

GRIIS_KEEP_COLS = (
    "scientificName", "canonicalName", "kingdom", "phylum", "class",
    "order", "family", "genus", "taxonomicStatus", "rank",
    "establishmentMeans", "degreeOfEstablishment",
)


class GBIFDownloader:
    """Thin REST client for GBIF occurrence + GRIIS checklist queries."""

    def __init__(self, base_url: str = GBIF_API, session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ HTTP

    def _get(self, endpoint: str, params: dict) -> dict:
        url = f"{self.base_url}/{endpoint}"
        r = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()

    # ----------------------------------------------------------- occurrences

    def query_occurrences(
        self,
        wkt: str,
        establishment_means: Iterable[str] = ESTABLISHMENT_MEANS,
        max_records: int = 100_000,
    ) -> gpd.GeoDataFrame:
        """Query GBIF for occurrences within ``wkt`` filtered by establishmentMeans.

        Returns a GeoDataFrame (EPSG:4326) of points, deduplicated on
        (species, lat, lon). Empty-but-schema-valid if no matches.
        """
        rows: list[dict] = []
        for est in establishment_means:
            log.info("GBIF occurrence search: establishmentMeans=%s", est)
            offset = 0
            while offset < max_records:
                page = self._get("occurrence/search", {
                    "geometry": wkt,
                    "establishmentMeans": est,
                    "hasCoordinate": "true",
                    "limit": GBIF_LIMIT,
                    "offset": offset,
                })
                results = page.get("results", [])
                rows.extend(results)
                if page.get("endOfRecords", True) or not results:
                    break
                offset += GBIF_LIMIT

        df = pd.DataFrame(rows)
        if df.empty:
            return _empty_occurrences_gdf()

        cols = [c for c in GBIF_COLS if c in df.columns]
        df = df[cols].drop_duplicates(
            subset=[c for c in ("species", "decimalLatitude", "decimalLongitude") if c in df.columns],
            keep="first",
        )
        return _occurrences_df_to_gdf(df)

    # ------------------------------------------------------------- GRIIS

    def fetch_griis_checklist(self, country_name: str) -> pd.DataFrame:
        """Fetch the GRIIS country checklist via GBIF dataset search."""
        log.info("GBIF GRIIS dataset search: %s", country_name)
        data = self._get("dataset/search", {"q": f"GRIIS {country_name}", "limit": 20})
        results = data.get("results", [])

        country_lower = country_name.lower().strip()
        griis_uuid: Optional[str] = None
        for ds in results:
            title_lower = ds.get("title", "").lower()
            if ("griis" in title_lower or "introduced and invasive" in title_lower) \
                    and country_lower in title_lower:
                griis_uuid = ds["key"]
                break
        if not griis_uuid:
            for ds in results:
                title_lower = ds.get("title", "").lower()
                if "griis" in title_lower or "introduced and invasive" in title_lower:
                    griis_uuid = ds["key"]
                    break

        if not griis_uuid:
            log.warning("No GRIIS dataset found for %s", country_name)
            return _empty_griis_df()

        species: list[dict] = []
        offset = 0
        while offset < MAX_GRIIS_SPECIES:
            page = self._get("species/search", {
                "datasetKey": griis_uuid,
                "limit": GBIF_LIMIT,
                "offset": offset,
            })
            recs = page.get("results", [])
            if not recs:
                break
            species.extend(recs)
            offset += GBIF_LIMIT
            if page.get("endOfRecords", True):
                break

        if not species:
            return _empty_griis_df()

        df = pd.DataFrame(species)
        cols = [c for c in GRIIS_KEEP_COLS if c in df.columns]
        df = df[cols].drop_duplicates()
        return df


# ---------------------------------------------------------------------- helpers


def _empty_griis_df() -> pd.DataFrame:
    return pd.DataFrame(columns=list(GRIIS_KEEP_COLS))


def _empty_occurrences_gdf() -> gpd.GeoDataFrame:
    cols = list(GBIF_COLS)
    df = pd.DataFrame({c: pd.Series(dtype="object") for c in cols})
    gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries([], crs="EPSG:4326"), crs="EPSG:4326")
    return gdf


def _occurrences_df_to_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Build a point GeoDataFrame from GBIF occurrence rows."""
    if df.empty:
        return _empty_occurrences_gdf()
    lats = pd.to_numeric(df.get("decimalLatitude"), errors="coerce")
    lons = pd.to_numeric(df.get("decimalLongitude"), errors="coerce")
    valid = lats.notna() & lons.notna()
    df = df.loc[valid].reset_index(drop=True)
    if df.empty:
        return _empty_occurrences_gdf()
    geometry = [Point(float(x), float(y)) for x, y in zip(lons.loc[valid], lats.loc[valid])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
