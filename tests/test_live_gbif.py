"""Live GBIF smoke test — gated by ``@pytest.mark.live`` (skipped by default).

Run with:
    python -m pytest -m live tests/test_live_gbif.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from _helpers import write_aoi_geojson


pytestmark = pytest.mark.live


def test_ulumbu_live_pipeline(tmp_path: Path):
    """Smoke: real GBIF call against a tiny Ulumbu-like AOI."""
    from pipeline import run

    aoi = write_aoi_geojson(tmp_path / "aoi.geojson")
    bundle = run(
        aoi_geojson=aoi,
        project="ulumbu",
        country_name="Indonesia",
        extraction_year=2024,
        output_root=tmp_path / "out",
        max_records=300,  # keep it fast
    )
    import json
    stats = json.loads((bundle / "statistics.json").read_text())
    assert "summary" in stats
    assert stats["_provenance"]["country_name"] == "Indonesia"
    assert (bundle / "manifest.json").exists()
