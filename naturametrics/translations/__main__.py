from . import missing_keys
from .pt import TRANSLATIONS_PT

problems = missing_keys()
if not problems:
    print(f"OK — {len(TRANSLATIONS_PT)} keys, all languages complete.")
else:
    for lang, keys in problems.items():
        print(f"{lang}: {len(keys)} mismatched keys — {sorted(keys)}")
    raise SystemExit(1)
