import hashlib
import json
from pathlib import Path

import pytest

from manifest import DISCIPLINE, SCHEMA_VERSION, verify_manifest, write_manifest


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


def _write_raw_manifest(bundle: Path, artefacts: list[dict]):
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "discipline": DISCIPLINE,
        "project": "ulumbu",
        "extraction_year": 2024,
        "generated_at_utc": "2024-01-01T00:00:00+00:00",
        "artefacts": artefacts,
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest))


def test_verify_manifest_clean(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    f = bundle / "statistics.json"
    f.write_text('{"summary":{}}')
    _write_raw_manifest(bundle, [{"kind": "statistics_json", "path": "statistics.json", "sha256": _sha256(f)}])

    assert verify_manifest(bundle) == []


def test_verify_manifest_tampered_bytes(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    f = bundle / "statistics.json"
    f.write_text('{"summary":{}}')
    _write_raw_manifest(bundle, [{"kind": "statistics_json", "path": "statistics.json", "sha256": _sha256(f)}])
    f.write_text('{"summary":{"tampered":true}}')

    assert verify_manifest(bundle) == ["statistics_json"]


def test_verify_manifest_missing_file(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _write_raw_manifest(bundle, [{"kind": "gone", "path": "gone.json", "sha256": "0" * 64}])

    assert verify_manifest(bundle) == ["gone"]


def test_verify_manifest_directory_entry_no_crash(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "subdir").mkdir()
    _write_raw_manifest(bundle, [{"kind": "a_dir", "path": ".", "sha256": "0" * 64}])

    assert verify_manifest(bundle) == ["a_dir"]


def test_verify_manifest_absolute_path_escapes_bundle(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("outside-bytes")
    _write_raw_manifest(bundle, [{"kind": "escaped", "path": str(outside), "sha256": _sha256(outside)}])

    assert verify_manifest(bundle) == ["escaped"]


def test_verify_manifest_dotdot_traversal_escapes_bundle(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("outside-bytes")
    _write_raw_manifest(bundle, [{"kind": "escaped", "path": "../secret.txt", "sha256": _sha256(outside)}])

    assert verify_manifest(bundle) == ["escaped"]
