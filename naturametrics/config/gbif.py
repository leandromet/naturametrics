"""GBIF occurrence data — endpoints, vocabularies and display palette.

**Why the REST API and not the BigQuery public dataset.** The original plan was
``bigquery-public-data.gbif.occurrences``. Measured against it, that table is
3.93 billion rows, and BigQuery bills *logical* bytes with no documented
clustering on this table — a viewport query needs ``decimallatitude``,
``decimallongitude`` and 8–10 taxonomy columns, which is a full-column scan of
all 3.93 B rows: 150–400 GB, roughly US$1–2.50 **per map pan** at $6.25/TiB. The
1 TiB/month free tier would be gone in four pans.

Brazil is 43 825 433 of those records (33 790 335 with usable coordinates) —
1.1 % of the table — so the affordable BigQuery path was always going to be a
materialised Brazil subset rather than the public table itself. The REST API
reaches the same 1.1 % for nothing, always fresh, with no derived table to
build, refresh or pay storage on. BigQuery remains the upgrade path if bulk
export or unlimited point density is ever needed; nothing here forecloses it.

**The API's own shape governs two design choices elsewhere:**

* One page of occurrences is capped at 300 records and weighs **2.2 MB** of
  verbatim Darwin Core (measured), against ~200 bytes per record of what is
  actually drawn. ``services/gbif.py`` therefore slims every record server-side
  before it reaches the browser — the reason this layer is proxied through
  ``/_gbif.geojson`` rather than fetched by Leaflet directly. There is no
  cheaper way to ask for the 2.2 MB in the first place: ``/occurrence/search``
  has no field-projection parameter (verified live — a ``fields=`` param is
  silently ignored, every record still comes back with its full ~82 keys) and
  the response is not gzip-compressed. Paging is the only lever GBIF gives us,
  which is what ``GBIF_MAX_PAGES`` (config/settings.py) and the fetch-in-
  parallel adaptive paging in ``services/gbif.py``'s ``_fetch()`` are for.
* Aggregates are free: ``limit=0`` with ``facet=`` returns counts without
  retrieving records at all, and ``facet=scientificName`` returns readable names
  rather than keys. That is what makes the species-in-buffer analysis
  (``services/gbif_buffers.py``) one ~1.1 s request per buffer instead of
  paging thousands of records.
"""

from __future__ import annotations

import os

API_BASE = os.environ.get("NM_GBIF_API_BASE", "https://api.gbif.org/v1")

OCCURRENCE_SEARCH = f"{API_BASE}/occurrence/search"
SPECIES_CHILDREN = f"{API_BASE}/species/{{key}}/children"
SPECIES_SUGGEST = f"{API_BASE}/species/suggest"
SPECIES_DETAIL = f"{API_BASE}/species/{{key}}"

#: Sent on every request. GBIF has no hard published rate limit but asks for
#: identifiable traffic, and the same contact address the IBAMA services already
#: use (services/embargos.py) is the one to give.
USER_AGENT = "naturametrics/1.0 (contact: leandromet@gmail.com)"

ATTRIBUTION = "GBIF.org — Global Biodiversity Information Facility"
PORTAL_URL = "https://www.gbif.org"

#: Everything is scoped to Brazil for now (the user's stated first cut). This is
#: the only place the country is named; widening later means adding a state var
#: that overrides it, not hunting for hard-coded "BR".
COUNTRY = "BR"

#: The GBIF nub/backbone dataset key. ``/species/suggest`` accepts a
#: ``datasetKey`` but does not reliably honour it, so services/gbif_taxa.py
#: filters the response on this value itself rather than trusting the query.
BACKBONE_DATASET_KEY = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"

# --------------------------------------------------------------------------- #
# The slim record
# --------------------------------------------------------------------------- #
#: GBIF JSON key → the property name carried in our GeoJSON. A record off the
#: wire is ~7.4 KB of verbatim Darwin Core; this is the ~200 bytes of it that
#: the tooltip, the legend colouring and the click handler actually read.
#: Anything not listed here is dropped in services/gbif.py::_slim.
SLIM_FIELDS = {
    "key": "gbif_id",
    "scientificName": "scientific_name",
    "species": "species",
    "genus": "genus",
    "family": "family",
    "order": "order",
    "class": "class_name",       # `class` is a Python keyword — renamed here,
    "phylum": "phylum",          # and the JS tooltip reads the renamed value.
    "kingdom": "kingdom",
    "taxonRank": "taxon_rank",
    "eventDate": "event_date",
    "year": "year",
    "basisOfRecord": "basis_of_record",
    "recordedBy": "recorded_by",
    "institutionCode": "institution_code",
    "datasetName": "dataset_name",
    "coordinateUncertaintyInMeters": "coordinate_uncertainty_m",
    "occurrenceStatus": "occurrence_status",
}

#: Fields drawn from a controlled vocabulary or a taxonomic backbone: every
#: legitimate value is one or two words. Some publishers ship records with
#: unrelated content packed into these — a collector string, a locality, a whole
#: verbatim row — which is a mapping error between the collection and GBIF, not
#: a long name. A value over this length in one of these fields is therefore
#: DROPPED rather than truncated: a 400-character "kingdom" is not a kingdom,
#: and truncating it to "Coleta realizada por Silva, J. em 12/03/199…" would
#: launder corrupt data into something that reads as real.
CONTROLLED_FIELDS = (
    "kingdom", "phylum", "class_name", "order", "family", "genus", "species",
    "taxon_rank", "basis_of_record", "occurrence_status",
)
CONTROLLED_MAX_CHARS = 60

#: Free-text fields where a long value is usually legitimate — a specimen with
#: six collectors runs past 100 characters honestly (measured: 108). Truncated
#: with an ellipsis rather than dropped, since the leading part is still the
#: answer to "who recorded this".
FREETEXT_MAX_CHARS = 180

#: Coordinates are pulled out into the geometry, not the properties — but the
#: click handler in leaflet_map.js reads `lat`/`lon` off properties (see its
#: `selectRef` call), so they are copied there too.
LAT_FIELD = "decimalLatitude"
LON_FIELD = "decimalLongitude"

# --------------------------------------------------------------------------- #
# Display
# --------------------------------------------------------------------------- #
#: One hue per kingdom — the coarsest split that still tells a reader whether
#: a dot is a bird, a tree or a fungus at a glance. Keyed by the kingdom NAME
#: as GBIF returns it, so the palette can be handed straight to
#: leaflet_map.js's styleFor() with `color_property: "kingdom"`.
KINGDOM_COLORS = {
    "Animalia": "d1495b",
    "Plantae":  "2a9d3f",
    "Fungi":    "8e5ea2",
    "Chromista": "00898f",
    "Protozoa": "d98c00",
    "Bacteria": "3d7ea6",
    "Archaea":  "7a7a7a",
    "Viruses":  "c2185b",
    "incertae sedis": "9e9e9e",
}
DEFAULT_COLOR = "9e9e9e"

# --------------------------------------------------------------------------- #
# Controlled vocabularies (filter dropdowns)
# --------------------------------------------------------------------------- #
#: GBIF's basisOfRecord enum, ordered by how many Brazilian records carry each
#: (verified live 2026-09-01) rather than alphabetically — the two that matter
#: account for 96 % of the country's 43.8 M records.
BASIS_OF_RECORD = [
    ("HUMAN_OBSERVATION", "Observação humana", "Human observation"),
    ("PRESERVED_SPECIMEN", "Espécime preservado", "Preserved specimen"),
    ("MATERIAL_SAMPLE", "Amostra de material", "Material sample"),
    ("MACHINE_OBSERVATION", "Observação automatizada", "Machine observation"),
    ("OCCURRENCE", "Ocorrência (sem tipo)", "Occurrence (untyped)"),
    ("MATERIAL_CITATION", "Citação de material", "Material citation"),
    ("LIVING_SPECIMEN", "Espécime vivo", "Living specimen"),
    ("FOSSIL_SPECIMEN", "Espécime fóssil", "Fossil specimen"),
    ("OBSERVATION", "Observação", "Observation"),
]

#: The eight GBIF backbone kingdoms, with their nub keys — the root of the
#: cascading taxonomy picker. Hard-coded rather than fetched because they are
#: the one level of the backbone that is genuinely fixed, and it saves a
#: round-trip before the user has chosen anything at all.
KINGDOMS = [
    (1, "Animalia"),
    (6, "Plantae"),
    (5, "Fungi"),
    (4, "Chromista"),
    (7, "Protozoa"),
    (3, "Bacteria"),
    (2, "Archaea"),
    (8, "Viruses"),
]

#: The ranks the accordion walks, in order. GBIF's backbone is strictly nested
#: through these, so each choice narrows the next one's children.
RANK_CHAIN = ("KINGDOM", "PHYLUM", "CLASS", "ORDER", "FAMILY", "GENUS", "SPECIES")

#: Brazil's 27 federative units as GADM level-1 GIDs, which is what GBIF's
#: `gadmGid` filter takes. The free-text `stateProvince` field is publisher-
#: supplied and inconsistent ("SP", "Sao Paulo", "São Paulo"); GADM is
#: interpreted by GBIF itself and is the only reliable state filter.
#: Verified live against /geocode/gadm/BRA/subdivisions (2026-09-01).
UF_GADM = [
    ("BRA.1_1", "AC", "Acre"),
    ("BRA.2_1", "AL", "Alagoas"),
    ("BRA.3_1", "AP", "Amapá"),
    ("BRA.4_1", "AM", "Amazonas"),
    ("BRA.5_1", "BA", "Bahia"),
    ("BRA.6_1", "CE", "Ceará"),
    ("BRA.7_1", "DF", "Distrito Federal"),
    ("BRA.8_1", "ES", "Espírito Santo"),
    ("BRA.9_1", "GO", "Goiás"),
    ("BRA.10_1", "MA", "Maranhão"),
    ("BRA.12_1", "MT", "Mato Grosso"),
    ("BRA.11_1", "MS", "Mato Grosso do Sul"),
    ("BRA.13_1", "MG", "Minas Gerais"),
    ("BRA.14_1", "PA", "Pará"),
    ("BRA.15_1", "PB", "Paraíba"),
    ("BRA.16_1", "PR", "Paraná"),
    ("BRA.17_1", "PE", "Pernambuco"),
    ("BRA.18_1", "PI", "Piauí"),
    ("BRA.19_1", "RJ", "Rio de Janeiro"),
    ("BRA.20_1", "RN", "Rio Grande do Norte"),
    ("BRA.21_1", "RS", "Rio Grande do Sul"),
    ("BRA.22_1", "RO", "Rondônia"),
    ("BRA.23_1", "RR", "Roraima"),
    ("BRA.24_1", "SC", "Santa Catarina"),
    ("BRA.25_1", "SP", "São Paulo"),
    ("BRA.26_1", "SE", "Sergipe"),
    ("BRA.27_1", "TO", "Tocantins"),
]

#: Earliest year offered by the year-range filter. GBIF holds Brazilian records
#: back to the 18th century, but a slider spanning 250 years wastes almost all
#: of its travel on a handful of specimens.
YEAR_MIN = 1900
