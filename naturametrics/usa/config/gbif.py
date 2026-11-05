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

#: The only country this page's GBIF layer ever queries. Widening later means
#: adding a state var that overrides it, not hunting for hard-coded "US".
COUNTRY = "US"

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

#: The 50 states and the District of Columbia as GADM level-1 GIDs — the same
#: `gadmGid` filter the Brazil page's UF_GADM feeds. VERIFIED LIVE against
#: /geocode/gadm/USA/subdivisions (2026-11-04): exactly what that endpoint returned,
#: sorted by name. GBIF's numbering is not alphabetical (Florida is USA.10_1).
#: Named ``PROVINCE_GADM`` to keep the USA page's code shape; the tuples are
#: (gid, postal abbreviation, name).
PROVINCE_GADM = [
    ("USA.1_1", "AL", "Alabama"),
    ("USA.2_1", "AK", "Alaska"),
    ("USA.3_1", "AZ", "Arizona"),
    ("USA.4_1", "AR", "Arkansas"),
    ("USA.5_1", "CA", "California"),
    ("USA.6_1", "CO", "Colorado"),
    ("USA.7_1", "CT", "Connecticut"),
    ("USA.8_1", "DE", "Delaware"),
    ("USA.9_1", "DC", "District of Columbia"),
    ("USA.10_1", "FL", "Florida"),
    ("USA.11_1", "GA", "Georgia"),
    ("USA.12_1", "HI", "Hawaii"),
    ("USA.13_1", "ID", "Idaho"),
    ("USA.14_1", "IL", "Illinois"),
    ("USA.15_1", "IN", "Indiana"),
    ("USA.16_1", "IA", "Iowa"),
    ("USA.17_1", "KS", "Kansas"),
    ("USA.18_1", "KY", "Kentucky"),
    ("USA.19_1", "LA", "Louisiana"),
    ("USA.20_1", "ME", "Maine"),
    ("USA.21_1", "MD", "Maryland"),
    ("USA.22_1", "MA", "Massachusetts"),
    ("USA.23_1", "MI", "Michigan"),
    ("USA.24_1", "MN", "Minnesota"),
    ("USA.25_1", "MS", "Mississippi"),
    ("USA.26_1", "MO", "Missouri"),
    ("USA.27_1", "MT", "Montana"),
    ("USA.28_1", "NE", "Nebraska"),
    ("USA.29_1", "NV", "Nevada"),
    ("USA.30_1", "NH", "New Hampshire"),
    ("USA.31_1", "NJ", "New Jersey"),
    ("USA.32_1", "NM", "New Mexico"),
    ("USA.33_1", "NY", "New York"),
    ("USA.34_1", "NC", "North Carolina"),
    ("USA.35_1", "ND", "North Dakota"),
    ("USA.36_1", "OH", "Ohio"),
    ("USA.37_1", "OK", "Oklahoma"),
    ("USA.38_1", "OR", "Oregon"),
    ("USA.39_1", "PA", "Pennsylvania"),
    ("USA.40_1", "RI", "Rhode Island"),
    ("USA.41_1", "SC", "South Carolina"),
    ("USA.42_1", "SD", "South Dakota"),
    ("USA.43_1", "TN", "Tennessee"),
    ("USA.44_1", "TX", "Texas"),
    ("USA.45_1", "UT", "Utah"),
    ("USA.46_1", "VT", "Vermont"),
    ("USA.47_1", "VA", "Virginia"),
    ("USA.48_1", "WA", "Washington"),
    ("USA.49_1", "WV", "West Virginia"),
    ("USA.50_1", "WI", "Wisconsin"),
    ("USA.51_1", "WY", "Wyoming"),
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
