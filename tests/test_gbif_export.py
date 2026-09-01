"""The GBIF species workbook, read back with an independent implementation.

Same reasoning as tests/test_exports.py: services/ods.py is a hand-written
format writer, and a hand-written format is exactly the kind of thing that
works on the author's machine and produces a file LibreOffice refuses to open.
So these read the output back through odfpy rather than trusting that what was
written is what was meant.

Offline throughout — nothing here touches GBIF. The rows are built by hand,
which is also the point: the export must be a pure function of what is already
in state, never a re-query, so that the file and the screen cannot disagree.
"""

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.config.settings import (  # noqa: E402
    GBIF_EXPORT_SPECIES_LIMIT,
    GBIF_FACET_LIMIT,
)
from naturametrics.services import gbif_export  # noqa: E402
from naturametrics.state._gbif import (  # noqa: E402
    GbifBufferRow,
    GbifKingdomRow,
    GbifSpeciesRow,
)

RADII = (0.5, 1.0, 2.0, 5.0, 10.0)


def _row(radius: float, species: list[tuple[str, int]], total: int,
         richness: int | None = None) -> GbifBufferRow:
    sp = [GbifSpeciesRow(name=n, count=c, count_label=str(c)) for n, c in species]
    return GbifBufferRow(
        radius_km=radius, radius_label=f"{radius:g} km",
        total=total, total_label=str(total),
        richness=richness if richness is not None else len(sp),
        richness_label=str(richness if richness is not None else len(sp)),
        species=sp, species_top=sp[:50],
        kingdoms=[GbifKingdomRow(name="Animalia", count=total)], error="")


@pytest.fixture
def rows() -> list[GbifBufferRow]:
    return [_row(r, [("Panthera onca", 10 * i), ("Araucaria angustifolia", 5 * i)],
                 total=100 * i)
            for i, r in enumerate(RADII, start=1)]


@pytest.fixture
def context():
    return [["  latitude", -3.1], ["  longitude", -60.02], ["  rótulo", "INPA"]]


def _read(data: bytes):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("odf", reason="odfpy is the independent reader")
    return pd.read_excel(io.BytesIO(data), sheet_name=None, engine="odf")


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_workbook_opens_and_has_metadata_plus_one_tab_per_radius(rows, context):
    data, name = gbif_export.build_ods(rows, context, [])
    assert name.endswith(".ods")
    sheets = _read(data)
    assert list(sheets)[0] == "metadados", "metadata must be the first tab"
    assert len(sheets) == 1 + len(RADII)


def test_radius_tab_names_sort_in_tab_order(rows, context):
    """A spreadsheet orders tabs as written, so "10km" must not land between
    "1km" and "2km" — hence the zero padding."""
    sheets = _read(gbif_export.build_ods(rows, context, [])[0])
    data_tabs = [s for s in sheets if s != "metadados"]
    assert data_tabs == ["especies_00_5km", "especies_01km", "especies_02km",
                         "especies_05km", "especies_10km"]
    assert data_tabs == sorted(data_tabs)


def test_species_rows_survive_the_round_trip(rows, context):
    sheets = _read(gbif_export.build_ods(rows, context, [])[0])
    # 1 km is the SECOND radius, so the fixture's i is 2 and its counts are
    # 20/10 out of a total of 200.
    tab = sheets["especies_01km"]
    assert list(tab.columns) == gbif_export.SPECIES_COLUMNS
    assert tab["especie"].tolist() == ["Panthera onca", "Araucaria angustifolia"]
    assert tab["registros"].tolist() == [20, 10]
    assert tab["raio_km"].tolist() == [1.0, 1.0]


def test_pct_is_the_species_share_of_its_own_radius(rows, context):
    """Each radius has a different total, so the percentage has to be computed
    against that radius rather than against the largest one."""
    sheets = _read(gbif_export.build_ods(rows, context, [])[0])
    # 2 km is the third radius: i=3, so counts are 30/15 out of a total of 300.
    tab = sheets["especies_02km"]
    assert tab["pct_do_raio"].tolist() == pytest.approx([10.0, 5.0])


# --------------------------------------------------------------------------- #
# The metadata tab is the deliverable, not decoration
# --------------------------------------------------------------------------- #
def _metadata_text(data: bytes) -> str:
    return _read(data)["metadados"].to_string()


def test_metadata_records_the_point_and_the_filters(rows, context):
    data, _ = gbif_export.build_ods(
        rows, context, [["  táxon", "Aves"], ["  UF", "AM"]])
    text = _metadata_text(data)
    assert "-3.1" in text and "-60.02" in text
    assert "INPA" in text
    assert "Aves" in text and "AM" in text


def test_metadata_says_so_when_no_filter_was_applied(rows, context):
    """An empty filter block would read as "the filters were lost", not as
    "there were none"."""
    assert "nenhum" in _metadata_text(gbif_export.build_ods(rows, context, [])[0])


def test_metadata_carries_the_licence_warning(rows, context):
    """GBIF aggregates CC-BY-NC data and this query does not exclude it. A
    spreadsheet that leaves that out is the one that gets used commercially."""
    text = _metadata_text(gbif_export.build_ods(rows, context, [])[0])
    assert "CC-BY-NC" in text
    assert "GBIF Occurrence Search" in text, "the required citation form"


def test_metadata_flags_a_richness_that_is_a_floor_not_a_count(context):
    """A radius that hits GBIF's facet ceiling has unknown richness. Reporting
    the ceiling as if it were a count is the failure this guards."""
    capped = _row(10.0, [("Panthera onca", 1)], total=99_999,
                  richness=GBIF_FACET_LIMIT)
    text = _metadata_text(gbif_export.build_ods([capped], context, [])[0])
    assert f"{GBIF_FACET_LIMIT}+" in text


def test_metadata_states_the_cumulative_disc_reading(rows, context):
    """The radii nest, so the tabs must not be summed. Nothing in the data
    tabs themselves conveys that."""
    assert "CUMULATIV" in _metadata_text(
        gbif_export.build_ods(rows, context, [])[0]).upper()


# --------------------------------------------------------------------------- #
# Safety and edges
# --------------------------------------------------------------------------- #
def test_a_species_name_cannot_smuggle_a_formula(context):
    """GBIF names are third-party strings landing in a cell someone opens in
    LibreOffice. services/ods.py defuses them; this pins that it still holds
    on this path."""
    row = _row(1.0, [("=HYPERLINK(\"http://evil\",\"x\")", 1)], total=1)
    tab = _read(gbif_export.build_ods([row], context, [])[0])["especies_01km"]
    assert str(tab["especie"].iloc[0]).startswith("'=")


def test_coordinates_are_numbers_not_apostrophe_escaped_text(rows, context):
    """A southern latitude starts with "-", which the formula guard would
    otherwise prefix with an apostrophe — see GbifMixin._gbif_export_context."""
    import zipfile
    data, _ = gbif_export.build_ods(rows, context, [])
    xml = zipfile.ZipFile(io.BytesIO(data)).read("content.xml").decode()
    assert 'office:value="-3.1"' in xml
    assert "'-3.1" not in xml


def test_empty_radius_still_gets_its_tab(context):
    """A filter that matches nothing at 500 m must produce an empty tab, not a
    missing one — a gap in the tab bar reads as a failed export."""
    sheets = _read(gbif_export.build_ods(
        [_row(0.5, [], total=0)], context, [])[0])
    assert "especies_00_5km" in sheets
    assert len(sheets["especies_00_5km"]) == 0


def test_zero_total_does_not_divide_by_zero(context):
    """`pct_do_raio` divides by the radius total, which can legitimately be 0
    when a facet returns rows the count does not."""
    row = _row(0.5, [("Panthera onca", 0)], total=0)
    tab = _read(gbif_export.build_ods([row], context, [])[0])["especies_00_5km"]
    assert tab["pct_do_raio"].tolist() == [0.0]


# --------------------------------------------------------------------------- #
# The flat CSV
# --------------------------------------------------------------------------- #
def test_csv_covers_every_radius_in_one_table(rows):
    data, name = gbif_export.build_csv(rows)
    assert name.endswith(".csv")
    lines = data.decode("utf-8").strip().splitlines()
    assert lines[0] == ",".join(gbif_export.CSV_COLUMNS)
    assert len(lines) == 1 + 2 * len(RADII)      # header + 2 species per radius
    # csv writes the float as-is, so 1.0 is "1.0", not "1".
    assert {line.split(",")[0] for line in lines[1:]} == {str(float(r))
                                                          for r in RADII}


def test_csv_and_ods_carry_the_same_numbers(rows, context):
    csv_text = gbif_export.build_csv(rows)[0].decode("utf-8")
    tab = _read(gbif_export.build_ods(rows, context, [])[0])["especies_05km"]
    for name, count in zip(tab["especie"], tab["registros"]):
        assert f"{name},{count}," in csv_text or f'"{name}",{count},' in csv_text


def test_export_limit_is_above_the_display_limit(rows):
    """The spreadsheet exists to carry more than the screen does; if these ever
    invert, the export silently becomes the weaker artefact."""
    from naturametrics.config.settings import GBIF_SPECIES_TABLE_LIMIT
    assert GBIF_EXPORT_SPECIES_LIMIT > GBIF_SPECIES_TABLE_LIMIT
