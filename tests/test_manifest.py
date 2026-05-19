import hashlib
import json
from pathlib import Path

import pytest

from manifest import DISCIPLINE, SCHEMA_VERSION, write_manifest


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_write_manifest_shape(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    a = bundle / "species_occurrences.gpkg"
    a.write_bytes(b"fake-gpkg-bytes")
    b = bundle / "statistics.json"
    b.write_text('{"summary":{}}')

    m = write_manifest(
        bundle,
        project="ulumbu",
        extraction_year=2024,
        artefacts={"species_occurrences_gpkg": a, "statistics_json": b},
    )

    assert m == bundle / "manifest.json"
    data = json.loads(m.read_text())
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["discipline"] == DISCIPLINE
    assert data["discipline"] == "invasives_baseline"
    assert data["project"] == "ulumbu"
    assert data["extraction_year"] == 2024
    assert {e["kind"] for e in data["artefacts"]} == {
        "species_occurrences_gpkg", "statistics_json"
    }
    for entry in data["artefacts"]:
        assert entry["sha256"] == _sha256(bundle / entry["path"])
        assert entry["bytes"] > 0
        assert entry["schema_version"] == SCHEMA_VERSION


def test_write_manifest_raises_on_missing_artefact(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with pytest.raises(FileNotFoundError):
        write_manifest(
            bundle,
            project="ulumbu",
            extraction_year=2024,
            artefacts={"missing": bundle / "nope.json"},
        )
