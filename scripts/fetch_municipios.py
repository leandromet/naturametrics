"""Build ``data/municipios.csv``.

Offline prep, run rarely, never imported by the app.

Ported from camposcope's script of the same name — same reasoning as this app's
own ``scripts/join_ifn_biomes.py``: the município *list* is a committed local
table, not a query, so the search box's type-ahead costs no round trip.
Geometry for framing the map comes from the shared Earth Engine asset instead
(``config.datasets.IBGE_MUNICIPIOS`` — the same asset camposcope's own
``IBGE_MUNICIPIOS`` reads, both apps running under the ee-leandromet project);
``cod_municipio_ibge`` joins the two.

Source: IBGE localidades API.

    python scripts/fetch_municipios.py
"""

from __future__ import annotations

import csv
import pathlib
import sys
import unicodedata

import requests

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "municipios.csv"
IBGE_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

FIELDS = ["cod_municipio_ibge", "nome", "uf", "nome_norm"]


def normalise(name: str) -> str:
    """Accent- and case-folded, for type-ahead matching.

    Users type "sao felix" and "SÃO FÉLIX"; both must find the same município.
    Stored rather than computed per keystroke — 5 570 rows is small, but the
    match runs on every character.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def main() -> int:
    print("fetching IBGE municípios …")
    data = requests.get(IBGE_MUNICIPIOS, timeout=(10, 120)).json()

    def dig(node, *path):
        """Walk a nested dict, treating a missing OR null level as absent.

        Some municípios come back with ``microrregiao: null`` — a plain
        ``.get(k, {})`` chain raises on those, because the key exists and its
        value is None.
        """
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node

    rows = []
    for m in data:
        # The UF sits four levels down, and the API has more than one nesting
        # shape — reach for it defensively rather than trusting a single path.
        uf = (dig(m, "microrregiao", "mesorregiao", "UF", "sigla")
              or dig(m, "regiao-imediata", "regiao-intermediaria", "UF", "sigla")
              or dig(m, "UF", "sigla"))
        if not uf:
            print(f"  ! no UF for {m.get('nome')!r} ({m.get('id')}), skipping",
                  file=sys.stderr)
            continue
        rows.append({
            "cod_municipio_ibge": m["id"],
            "nome": m["nome"],
            "uf": uf,
            "nome_norm": normalise(m["nome"]),
        })

    rows.sort(key=lambda r: (r["uf"], r["nome_norm"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT} — {len(rows)} municípios, {size_kb:.0f} kB")
    if not (5500 <= len(rows) <= 5600):
        print(f"  ! expected ~5 570 municípios, got {len(rows)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
