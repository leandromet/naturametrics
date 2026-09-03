"""GBIF occurrence data for the Canada page — endpoints, vocabularies and
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

#: The only country this page's GBIF layer ever queries. Widening later means
#: adding a state var that overrides it, not hunting for hard-coded "CA".
COUNTRY = "CA"

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
#: Same list and order as the Brazil page. Checked live against Canadian
#: records (2026-09-03): the top four are identical (HUMAN_OBSERVATION,
#: PRESERVED_SPECIMEN, MATERIAL_SAMPLE, MACHINE_OBSERVATION), so the five
#: shown in the panel (``BASIS_OF_RECORD[:5]``) barely change — OBSERVATION
#: edges out OCCURRENCE for 5th place here, not worth a second, drifting copy
#: of an otherwise-identical GBIF-global list.
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

#: Canada's 10 provinces and 3 territories as GADM level-1 GIDs — the same
#: `gadmGid` filter the Brazil page's UF_GADM feeds. VERIFIED LIVE against
#: /geocode/gadm/CAN/subdivisions (2026-09-03): all 13 ids below are exactly
#: what that endpoint returned, not the standard "CAN.<n>_1 in alphabetical
#: order" guess (GBIF's own numbering is not alphabetical — e.g. Yukon is
#: CAN.13_1, not CAN.3_1).
PROVINCE_GADM = [
    ("CAN.1_1", "AB", "Alberta"),
    ("CAN.2_1", "BC", "British Columbia"),
    ("CAN.3_1", "MB", "Manitoba"),
    ("CAN.4_1", "NB", "New Brunswick"),
    ("CAN.5_1", "NL", "Newfoundland and Labrador"),
    ("CAN.6_1", "NT", "Northwest Territories"),
    ("CAN.7_1", "NS", "Nova Scotia"),
    ("CAN.8_1", "NU", "Nunavut"),
    ("CAN.9_1", "ON", "Ontario"),
    ("CAN.10_1", "PE", "Prince Edward Island"),
    ("CAN.11_1", "QC", "Québec"),
    ("CAN.12_1", "SK", "Saskatchewan"),
    ("CAN.13_1", "YT", "Yukon"),
]

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
