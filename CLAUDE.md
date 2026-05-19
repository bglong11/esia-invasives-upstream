# CLAUDE.md

Invasives **Upstream Pipeline** for the ESIA stack. Headless GBIF-driven query of invasive/introduced/naturalised species occurrences clipped to a project AOI, plus the GRIIS country checklist, followed by taxonomic + establishment-means breakdowns and top-species rollups. Output feeds the `invasives_baseline` Discipline (Baseline App `invasives`) in `~/github-ubuntu/esia-baseline-canonicalization/`.

## Authoritative references

Read these *before* designing anything in this repo:

- `~/github-ubuntu/esia-baseline-canonicalization/docs/adr/0015-invasives-baseline-app.md` — the governing ADR.
- `~/github-ubuntu/esia-baseline-canonicalization/docs/adr/0011-buildings-baseline-app.md` — the closest precedent (REST-API source, polygon AOI, vector-primary).
- `~/github-ubuntu/esia-baseline-canonicalization/docs/adr/0006-...md` — names this repo's architectural role.
- `~/github-ubuntu/esia-baseline-canonicalization/docs/adr/0004-...md` — forbids ESIA-prose / narrative / PDF output here.
- `~/github-ubuntu/esia-invasives/` — the strip-and-fork source. Only `query_invasives.py` Phases 1+2 are lifted; `generate_report.py`, `research_species.py`, Phases 3+4 are out of scope.

## Hard rules

- **No ESIA section prose.** No markdown reports, no PDF generation, no LLM narrative.
- **No bundle assembly.** This repo emits flat payload files (`species_occurrences.gpkg`, `griis_checklist.csv`, `statistics.json`, `aoi.geojson`) + `manifest.json`. Bundle shaping is the consuming Baseline App's job.
- **No figure rendering.** No matplotlib plots, no PNG previews. Downstream re-renders from `statistics.json`.
- **No LLM / Pydantic-AI / Tavily / report agents.**
- **No PDF / DOCX export.**
- **No Google Maps / static-map output.**
- Idempotent stages; GBIF REST queries are deterministic given AOI + filter.

## Status

v1 per ADR-0015. Local-only until HITL sign-off; push to `bglong11/esia-invasives-upstream` deferred.

## Run

```bash
# unit + non-live tests
python -m pytest -m "not live"

# live GBIF smoke test (network required)
python -m pytest -m live tests/test_live_gbif.py
```
