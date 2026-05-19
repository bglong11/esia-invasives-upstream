"""Analytical primitives for invasive species occurrences.

Computes:
    * summary stats (occurrence + species counts, GRIIS + IUCN-100 counts)
    * taxonomic breakdown (per-kingdom and per-class)
    * establishment-means breakdown
    * top-N species by observation count
    * IUCN-100-worst + GRIIS-listed flagging on the occurrence GDF

NO matplotlib. NO LLM. All outputs are JSON-serialisable primitives.
"""

from __future__ import annotations

from typing import Iterable

import geopandas as gpd
import pandas as pd


# IUCN "100 of the World's Worst Invasive Alien Species" — preserved verbatim
# from ~/github-ubuntu/esia-invasives/query_invasives.py
IUCN_100_WORST: frozenset[str] = frozenset({
    "Acacia mearnsii", "Achatina fulica", "Acridotheres tristis",
    "Aedes albopictus", "Anopheles quadrimaculatus", "Anoplolepis gracilipes",
    "Aphanomyces astaci", "Ardisia elliptica", "Arundo donax",
    "Batrachochytrium dendrobatidis", "Bemisia tabaci", "Boiga irregularis",
    "Bufo marinus", "Capra hircus", "Caulerpa taxifolia",
    "Cecropia peltata", "Cercopagis pengoi", "Chromolaena odorata",
    "Cinchona pubescens", "Clidemia hirta", "Coptotermes formosanus",
    "Cryphonectria parasitica", "Cyperus rotundus", "Dreissena polymorpha",
    "Eichhornia crassipes", "Eleutherodactylus coqui", "Euglandina rosea",
    "Euphorbia esula", "Felis catus", "Gambusia affinis",
    "Hedychium gardnerianum", "Herpestes javanicus", "Imperata cylindrica",
    "Lantana camara", "Lates niloticus", "Leucaena leucocephala",
    "Ligustrum robustum", "Linepithema humile", "Lymantria dispar",
    "Lythrum salicaria", "Macaca fascicularis", "Melaleuca quinquenervia",
    "Miconia calvescens", "Mikania micrantha", "Mnemiopsis leidyi",
    "Mus musculus", "Mustela erminea", "Myocastor coypus",
    "Myrica faya", "Mytilus galloprovincialis", "Oncorhynchus mykiss",
    "Ophiostoma ulmi", "Opuntia stricta", "Oryctolagus cuniculus",
    "Pheidole megacephala", "Phytophthora cinnamomi", "Pinus pinaster",
    "Plasmodium relictum", "Pomacea canaliculata", "Prosopis glandulosa",
    "Psidium cattleianum", "Pueraria montana", "Rattus rattus",
    "Rubus ellipticus", "Salmo trutta", "Schinus terebinthifolius",
    "Sciurus carolinensis", "Solenopsis invicta", "Spathodea campanulata",
    "Sphagneticola trilobata", "Sturnus vulgaris", "Sus scrofa",
    "Trachemys scripta elegans", "Trichosurus vulpecula", "Trogoderma granarium",
    "Undaria pinnatifida", "Ulex europaeus", "Vespula vulgaris",
    "Vulpes vulpes", "Wasmannia auropunctata",
})


def flag_iucn_100(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add boolean ``iucn_100_flag`` column. Returns a copy."""
    gdf = gdf.copy()
    if gdf.empty or "species" not in gdf.columns:
        gdf["iucn_100_flag"] = pd.Series([False] * len(gdf), dtype="bool")
        return gdf
    gdf["iucn_100_flag"] = gdf["species"].isin(IUCN_100_WORST)
    return gdf


def flag_griis_listed(gdf: gpd.GeoDataFrame, griis_species: Iterable[str]) -> gpd.GeoDataFrame:
    """Add boolean ``griis_listed`` column. Returns a copy."""
    griis_set = {s for s in griis_species if isinstance(s, str) and s}
    gdf = gdf.copy()
    if gdf.empty or "species" not in gdf.columns:
        gdf["griis_listed"] = pd.Series([False] * len(gdf), dtype="bool")
        return gdf
    gdf["griis_listed"] = gdf["species"].isin(griis_set)
    return gdf


def compute_taxonomic_breakdown(gdf: gpd.GeoDataFrame) -> dict:
    """Per-kingdom and per-class occurrence counts."""
    if gdf.empty:
        return {"per_kingdom": {}, "per_class": {}}
    out: dict = {}
    for col, key in (("kingdom", "per_kingdom"), ("class", "per_class")):
        if col in gdf.columns:
            counts = gdf[col].dropna().astype(str).value_counts()
            out[key] = {str(k): int(v) for k, v in counts.items()}
        else:
            out[key] = {}
    return out


def compute_establishment_breakdown(gdf: gpd.GeoDataFrame) -> dict:
    """Counts per ``establishmentMeans`` value."""
    if gdf.empty or "establishmentMeans" not in gdf.columns:
        return {}
    counts = gdf["establishmentMeans"].dropna().astype(str).value_counts()
    return {str(k): int(v) for k, v in counts.items()}


def compute_top_species(gdf: gpd.GeoDataFrame, top_n: int = 20) -> list[dict]:
    """Top-N species by observation count."""
    if gdf.empty or "species" not in gdf.columns:
        return []
    species_series = gdf["species"].dropna().astype(str)
    if species_series.empty:
        return []
    counts = species_series.value_counts().head(top_n)
    out: list[dict] = []
    for sp, count in counts.items():
        sp_rows = gdf.loc[gdf["species"] == sp]
        iucn = bool(sp_rows["iucn_100_flag"].any()) if "iucn_100_flag" in sp_rows.columns else (sp in IUCN_100_WORST)
        griis = bool(sp_rows["griis_listed"].any()) if "griis_listed" in sp_rows.columns else False
        out.append({
            "species": sp,
            "count": int(count),
            "iucn_100_flag": iucn,
            "griis_listed": griis,
        })
    return out


def compute_summary_stats(
    gdf: gpd.GeoDataFrame,
    griis_df: pd.DataFrame,
    aoi_area_km2: float,
) -> dict:
    """Single consolidated summary dict."""
    occ_count = int(len(gdf))
    species_count = (
        int(gdf["species"].dropna().nunique()) if not gdf.empty and "species" in gdf.columns else 0
    )
    griis_count = int(len(griis_df)) if griis_df is not None else 0
    iucn_count = (
        int(gdf["iucn_100_flag"].sum()) if not gdf.empty and "iucn_100_flag" in gdf.columns else 0
    )
    return {
        "gbif_occurrence_count": occ_count,
        "gbif_species_count": species_count,
        "griis_species_count": griis_count,
        "iucn_100_count": iucn_count,
        "aoi_area_km2": round(float(aoi_area_km2), 4),
    }
