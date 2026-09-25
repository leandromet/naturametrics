"""Vendor the canonical report_kit into Camposcope and Yvynation (doc/14 §2.1).

    python scripts/sync_report_kit.py            # rewrite MANIFEST, copy to both apps
    python scripts/sync_report_kit.py --check    # verify every copy, change nothing
    python scripts/sync_report_kit.py --manifest-only

The canonical copy is naturametrics/report_kit/. MANIFEST lists the sha256 of
every file in it; each app's tests/test_report_kit_manifest.py recomputes the
hashes of its own copy against that MANIFEST, so a fix made in a vendored copy
fails that app's tests instead of being silently lost at the next sync.
A target app whose checkout is missing is reported and skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "naturametrics" / "report_kit"
TARGETS = {
    "camposcope": Path("/server/camposcope/camposcope/report_kit"),
    "yvynation": Path("/home/leandromb/google_eengine/yvynation/reflex_app/yvynation/report_kit"),
}
SKIP_DIRS = {"__pycache__"}
MANIFEST = "MANIFEST"


def kit_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*")
                  if p.is_file() and p.name != MANIFEST
                  and not SKIP_DIRS.intersection(p.relative_to(base).parts))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_text(base: Path) -> str:
    lines = [f"{digest(p)}  {p.relative_to(base).as_posix()}" for p in kit_files(base)]
    return "\n".join(lines) + "\n"


def read_manifest(base: Path) -> dict[str, str]:
    out = {}
    for line in (base / MANIFEST).read_text().splitlines():
        if line.strip():
            h, rel = line.split("  ", 1)
            out[rel] = h
    return out


def verify(base: Path) -> list[str]:
    """Differences between ``base`` and its MANIFEST (empty when clean)."""
    if not (base / MANIFEST).exists():
        return ["MANIFEST missing"]
    want = read_manifest(base)
    have = {p.relative_to(base).as_posix(): digest(p) for p in kit_files(base)}
    problems = [f"modified: {r}" for r in want if r in have and have[r] != want[r]]
    problems += [f"missing: {r}" for r in want if r not in have]
    problems += [f"unexpected: {r}" for r in have if r not in want]
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--manifest-only", action="store_true")
    args = ap.parse_args()

    if args.check:
        bad = 0
        for name, base in [("naturametrics", KIT), *TARGETS.items()]:
            if not base.exists():
                print(f"{name}: not present ({base})")
                continue
            problems = verify(base)
            if base != KIT and (base / MANIFEST).exists() and (KIT / MANIFEST).exists() \
                    and (base / MANIFEST).read_text() != (KIT / MANIFEST).read_text():
                problems.append("MANIFEST differs from the canonical one (stale copy)")
            print(f"{name}: {'OK' if not problems else '; '.join(problems)}")
            bad += bool(problems)
        return 1 if bad else 0

    (KIT / MANIFEST).write_text(manifest_text(KIT))
    print(f"MANIFEST: {len(kit_files(KIT))} files")
    if args.manifest_only:
        return 0
    for name, dest in TARGETS.items():
        if not dest.parent.exists():
            print(f"{name}: skipped, {dest.parent} not found")
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(KIT, dest, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        problems = verify(dest)
        print(f"{name}: {'synced' if not problems else 'FAILED ' + '; '.join(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
