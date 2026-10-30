"""Copy the suite's shared single files into Camposcope and Yvynation, by hash.

    python scripts/sync_shared_files.py            # copy, then rewrite every manifest
    python scripts/sync_shared_files.py --check    # verify every copy, change nothing

The report kit is a package and has its own sync (``sync_report_kit.py``). These
are loose files that sit at a different path in each app — the address search,
the quick-start card, the links between the platforms, the MapBiomas legend and
the scrolling demonstrations' kit — so each app keeps
its own ``tests/shared_files.sha256`` with its own paths, and its
``tests/test_shared_files.py`` (the same file in all three apps) recomputes the
hashes. A fix made in a copy instead of here fails that app's tests rather than
being silently overwritten by the next sync.

Naturametrics holds the canonical copies, as it does for the report kit. An app
whose checkout is missing is reported and skipped.

An app takes only the files listed for it: muda-clima is a FastAPI app,
not Reflex, so it shares the address search, the MapBiomas legend and the
demonstrations' kit CSS/JS only.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

#: App roots: the directory holding each app's ``tests/``.
APPS = {
    "naturametrics": Path(__file__).resolve().parent.parent,
    "camposcope": Path("/server/camposcope"),
    "yvynation": Path("/home/leandromb/google_eengine/yvynation/reflex_app"),
    "muda_clima": Path("/server/2026_projeto_clima/muda-clima"),
    # the portal's long stories (public/historias/) run on the same kit
    "portal": Path("/media/leandromb/db_lin/gitstore/leandromet/umaterra-portal"),
}
CANONICAL = "naturametrics"

#: Each shared file's path in each app, relative to that app's root.
SHARED = {
    "address": {
        "naturametrics": "naturametrics/services/address.py",
        "camposcope": "camposcope/services/address.py",
        "yvynation": "yvynation/utils/address.py",
        "muda_clima": "app/services/sources/address.py",
    },
    "quickstart": {
        "naturametrics": "naturametrics/components/quickstart.py",
        "camposcope": "camposcope/components/quickstart.py",
        "yvynation": "yvynation/components/quickstart.py",
    },
    "mapbiomas_legend": {
        "naturametrics": "naturametrics/config/mapbiomas_legend.py",
        "camposcope": "camposcope/config/mapbiomas_legend.py",
        "yvynation": "yvynation/config/mapbiomas_legend.py",
        "muda_clima": "app/impact/mapbiomas_legend.py",
    },
    "suite_links": {
        "naturametrics": "naturametrics/components/suite_links.py",
        "camposcope": "camposcope/components/suite_links.py",
        "yvynation": "yvynation/components/suite_links.py",
    },
    # The scrolling demonstrations' kit (reportagem/kit.py wraps an article in
    # a Reflex page; muda-clima serves the CSS/JS from its own static dir).
    "reportagem_kit_py": {
        "naturametrics": "naturametrics/reportagem/kit.py",
        "camposcope": "camposcope/reportagem/kit.py",
        "yvynation": "yvynation/reportagem/kit.py",
    },
    "reportagem_kit_js": {
        "naturametrics": "naturametrics/reportagem/kit.js",
        "camposcope": "camposcope/reportagem/kit.js",
        "yvynation": "yvynation/reportagem/kit.js",
        "muda_clima": "app/web/static/reportagem/kit.js",
        "portal": "public/historias/kit.js",
    },
    "reportagem_kit_css": {
        "naturametrics": "naturametrics/reportagem/kit.css",
        "camposcope": "camposcope/reportagem/kit.css",
        "yvynation": "yvynation/reportagem/kit.css",
        "muda_clima": "app/web/static/reportagem/kit.css",
        "portal": "public/historias/kit.css",
    },
}
MANIFEST = Path("tests") / "shared_files.sha256"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_text(app: str) -> str:
    """``<sha256>  <path>`` per shared file, for ``app``'s own paths. Every app's
    manifest carries the canonical digests, so a copy that differs fails."""
    root = APPS[CANONICAL]
    lines = [f"{digest(root / paths[CANONICAL])}  {paths[app]}"
             for paths in SHARED.values() if app in paths]
    return "\n".join(lines) + "\n"


def verify(app: str) -> list[str]:
    root = APPS[app]
    problems = []
    for name, paths in SHARED.items():
        if app not in paths:
            continue
        mine, canon = root / paths[app], APPS[CANONICAL] / paths[CANONICAL]
        if not mine.exists():
            problems.append(f"missing: {paths[app]}")
        elif digest(mine) != digest(canon):
            problems.append(f"differs from canonical: {paths[app]}")
    if not (root / MANIFEST).exists():
        problems.append(f"{MANIFEST} missing")
    elif (root / MANIFEST).read_text() != manifest_text(app):
        problems.append(f"{MANIFEST} is stale")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    present = {a: r for a, r in APPS.items() if r.exists()}
    for app in APPS.keys() - present.keys():
        print(f"{app}: skipped, {APPS[app]} not found")

    if args.check:
        bad = 0
        for app in present:
            problems = verify(app)
            print(f"{app}: {'OK' if not problems else '; '.join(problems)}")
            bad += bool(problems)
        return 1 if bad else 0

    for app in present:
        if app != CANONICAL:
            for paths in SHARED.values():
                if app not in paths:
                    continue
                (present[app] / paths[app]).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(APPS[CANONICAL] / paths[CANONICAL], present[app] / paths[app])
        (present[app] / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
        (present[app] / MANIFEST).write_text(manifest_text(app))
        problems = verify(app)
        print(f"{app}: {'synced' if not problems else 'FAILED ' + '; '.join(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
