"""Write manifest.json — artefact listing with SHA256.

Mirrors ``esia-buildings-upstream/src/manifest.py`` with the discipline
identifier swapped to ``invasives_baseline``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


SCHEMA_VERSION = "1.0"
DISCIPLINE = "invasives_baseline"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(
    bundle_dir: Path,
    project: str,
    extraction_year: int,
    artefacts: Mapping[str, Path] | Iterable[tuple[str, Path]],
) -> Path:
    """Write manifest.json listing each artefact's relative path + SHA256."""
    bundle_dir = Path(bundle_dir)
    items = artefacts.items() if isinstance(artefacts, Mapping) else artefacts

    entries: list[dict] = []
    for kind, path in items:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"manifest: artefact missing on disk: {path}")
        entries.append({
            "kind": kind,
            "path": str(path.relative_to(bundle_dir)),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "schema_version": SCHEMA_VERSION,
        })

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "discipline": DISCIPLINE,
        "project": project,
        "extraction_year": int(extraction_year),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artefacts": entries,
    }

    out = bundle_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return out


def verify_manifest(bundle_dir: Path) -> list[str]:
    """Recompute each artefact's SHA256 against manifest.json; return kinds
    that are missing or hash-mismatched. Empty list = bundle intact."""
    bundle_dir = Path(bundle_dir)
    bundle_resolved = bundle_dir.resolve()
    manifest = json.loads((bundle_dir / "manifest.json").read_text())

    mismatched: list[str] = []
    for entry in manifest["artefacts"]:
        try:
            p = (bundle_dir / entry["path"]).resolve()
            intact = (p.is_relative_to(bundle_resolved) and p.is_file()
                      and _sha256(p) == entry["sha256"])
        except (OSError, RuntimeError, ValueError):
            # resolve() raises RuntimeError on a symlink loop and ValueError on
            # an embedded NUL byte. A malformed manifest must be REPORTED, not
            # crash the verifier whose whole job is detecting malformed
            # manifests -- a crash is indistinguishable from a broken tool.
            intact = False
        if not intact:
            mismatched.append(entry["kind"])
    return mismatched
