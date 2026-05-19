import sys
from pathlib import Path

# Mirror the repo-level conftest so plain `pytest tests/...` works too.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: live network test against the real GBIF API (skipped by default)",
    )
