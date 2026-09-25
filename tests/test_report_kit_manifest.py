"""The vendored report_kit matches its MANIFEST (doc/14 §2.1).

Same file in Naturametrics (canonical), Camposcope and Yvynation. It finds the
app's own report_kit/ below the repository root, so it needs no per-app edit.
A failure means someone edited a copy: make the fix in
/server/naturametrics/naturametrics/report_kit/ and run
``python scripts/sync_report_kit.py`` there instead.
"""

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _kit_dir() -> Path:
    found = [p.parent for p in REPO.rglob("report_kit/MANIFEST")
             if ".venv" not in p.parts and ".web" not in p.parts]
    assert len(found) == 1, f"expected one report_kit/MANIFEST under {REPO}, got {found}"
    return found[0]


def test_every_kit_file_matches_the_manifest():
    kit = _kit_dir()
    want = {}
    for line in (kit / "MANIFEST").read_text().splitlines():
        if line.strip():
            digest, rel = line.split("  ", 1)
            want[rel] = digest
    have = {p.relative_to(kit).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in kit.rglob("*")
            if p.is_file() and p.name != "MANIFEST" and "__pycache__" not in p.parts}
    assert set(have) == set(want), {"missing": sorted(set(want) - set(have)),
                                    "unexpected": sorted(set(have) - set(want))}
    changed = sorted(r for r in want if have[r] != want[r])
    assert not changed, f"edited outside the canonical copy: {changed}"
