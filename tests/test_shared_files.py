"""The suite's shared single files match tests/shared_files.sha256.

Same file in Naturametrics (canonical), Camposcope and Yvynation; each app's
manifest lists its own paths with the canonical digests. A failure means a copy
was edited in place: make the fix in Naturametrics and run
``python scripts/sync_shared_files.py`` there instead.
"""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).resolve().parent / "shared_files.sha256"


def _entries():
    out = {}
    for line in MANIFEST.read_text().splitlines():
        if line.strip():
            digest, rel = line.split("  ", 1)
            out[rel] = digest
    return out


def test_the_manifest_lists_the_three_shared_files():
    names = sorted(Path(rel).name for rel in _entries())
    assert names == ["address.py", "quickstart.py", "suite_links.py"], names


def test_every_shared_file_matches_the_manifest():
    changed = sorted(rel for rel, digest in _entries().items()
                     if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest)
    assert not changed, f"edited outside the canonical copy: {changed}"
