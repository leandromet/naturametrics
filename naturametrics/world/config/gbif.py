"""GBIF occurrence data for the USA page — endpoints, vocabularies and
display palette.

Same REST-vs-BigQuery reasoning as the Brazil page's ``config/gbif.py``; see
that file for the full cost analysis, which is a property of the GBIF API and
the app's billing exposure, not of either country. Only what is genuinely
country-specific is redefined here: ``COUNTRY`` and the province/territory
GADM table below. Everything else — the slim field map, the controlled
vocabularies, the eight backbone kingdoms, the palette — is GBIF-global and
copied unchanged from the Brazil file.
"""

from __future__ import annotations

import os

API_BASE = os.environ.get("NM_GBIF_API_BASE", "https://api.gbif.org/v1")

OCCURRENCE_SEARCH = f"{API_BASE}/occurrence/search"
SPECIES_CHILDREN = f"{API_BASE}/species/{{key}}/children"
SPECIES_SUGGEST = f"{API_BASE}/species/suggest"
SPECIES_DETAIL = f"{API_BASE}/species/{{key}}"

#: Sent on every request. Same contact address as the Brazil page and the
#: IBAMA services (naturametrics/services/embargos.py) — one app, one contact.
USER_AGENT = "naturametrics/1.0 (contact: leandromet@gmail.com)"

ATTRIBUTION = "GBIF.org — Global Biodiversity Information Facility"
PORTAL_URL = "https://www.gbif.org"

#: No country filter: the world page's GBIF layer queries every country (the map's viewport narrows it).
#: A country code here would restrict it; empty means "all".
COUNTRY = ""

#: The GBIF nub/backbone dataset key — the same backbone for every country,
#: since GBIF has exactly one taxonomic backbone regardless of who is querying.
BACKBONE_DATASET_KEY = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"

# --------------------------------------------------------------------------- #
# The slim record — identical to the Brazil page (config/gbif.py::SLIM_FIELDS)
# --------------------------------------------------------------------------- #
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

#: See the Brazil file's own comment on why a long value here is DROPPED
#: rather than truncated — the same publisher-side data-quality issue is not
#: specific to one country's records.
CONTROLLED_FIELDS = (
    "kingdom", "phylum", "class_name", "order", "family", "genus", "species",
    "taxon_rank", "basis_of_record", "occurrence_status",
)
CONTROLLED_MAX_CHARS = 60
FREETEXT_MAX_CHARS = 180

LAT_FIELD = "decimalLatitude"
LON_FIELD = "decimalLongitude"

# --------------------------------------------------------------------------- #
# Display
# --------------------------------------------------------------------------- #
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
#: The nine GBIF record types, ordered by their count for country=US (checked live 2026-11-04: human
#: observation 1.15 billion, preserved specimen 35 million, material sample 16 million, observation
#: 8.5 million, machine observation 2.7 million, …), so the five the panel shows are the commonest here.
#: (The Brazil/Canada pages keep the Brazil list and order.)
BASIS_OF_RECORD = [
    ("HUMAN_OBSERVATION", "Observação humana", "Human observation"),
    ("PRESERVED_SPECIMEN", "Espécime preservado", "Preserved specimen"),
    ("MATERIAL_SAMPLE", "Amostra de material", "Material sample"),
    ("OBSERVATION", "Observação", "Observation"),
    ("MACHINE_OBSERVATION", "Observação automatizada", "Machine observation"),
    ("FOSSIL_SPECIMEN", "Espécime fóssil", "Fossil specimen"),
    ("OCCURRENCE", "Ocorrência (sem tipo)", "Occurrence (untyped)"),
    ("MATERIAL_CITATION", "Citação de material", "Material citation"),
    ("LIVING_SPECIMEN", "Espécime vivo", "Living specimen"),
]

#: The eight GBIF backbone kingdoms — fixed and global, not per-country.
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

RANK_CHAIN = ("KINGDOM", "PHYLUM", "CLASS", "ORDER", "FAMILY", "GENUS", "SPECIES")

#: No sub-national list for the world: the USA page's state filter (GADM level-1 GIDs) has no global
#: counterpart that fits a dropdown. Kept as an empty list so the panel and state code read the same.
PROVINCE_GADM: list[tuple[str, str, str]] = []

#: Same floor as the Brazil page — GBIF's coverage depth is comparable, and a
#: quarter-millennium slider would waste nearly all its travel either way.
YEAR_MIN = 1900

__all__ = [
    "API_BASE", "OCCURRENCE_SEARCH", "SPECIES_CHILDREN", "SPECIES_SUGGEST",
    "SPECIES_DETAIL", "USER_AGENT", "ATTRIBUTION", "PORTAL_URL", "COUNTRY",
    "BACKBONE_DATASET_KEY", "SLIM_FIELDS", "CONTROLLED_FIELDS",
    "CONTROLLED_MAX_CHARS", "FREETEXT_MAX_CHARS", "LAT_FIELD", "LON_FIELD",
    "KINGDOM_COLORS", "DEFAULT_COLOR", "BASIS_OF_RECORD", "KINGDOMS",
    "RANK_CHAIN", "PROVINCE_GADM", "YEAR_MIN",
]
