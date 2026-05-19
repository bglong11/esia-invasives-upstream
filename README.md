# esia-invasives-upstream

Upstream Pipeline for the `invasives_baseline` Discipline of the ESIA Baseline Canonicalization framework.

Queries **GBIF occurrences** (filtered by `establishmentMeans` ∈ {INVASIVE, INTRODUCED, NATURALISED}) and the **GRIIS country checklist** for a project AOI, computes taxonomic + establishment-means + top-species rollups, flags the IUCN-100 worst invasives, and writes a flat analytical payload:

```
data/outputs/<project>/invasives/<year>/
  species_occurrences.gpkg   # vector points + taxonomy + flags
  griis_checklist.csv        # full country checklist
  statistics.json            # summary + taxonomic / establishment / top-species
  aoi.geojson                # frozen input AOI
  manifest.json              # SHA256 + paths for each artefact
```

See `CLAUDE.md` for architectural rules and the governing ADR-0015 in the parent repo.

## Usage

```python
from pipeline import run

run(
    aoi_geojson="path/to/aoi.geojson",
    project="ulumbu",
    country_name="Indonesia",
    extraction_year=2024,
    output_root="data/outputs",
)
```

## Test

```bash
python -m pytest -m "not live"           # unit + integration (mocked)
python -m pytest -m live                 # live GBIF smoke test
```
