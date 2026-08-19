"""services/user_points.py — the pasted coordinate list parser, and the
SelectionSpec branch that lets it reuse the whole conglomerado export pipeline.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.config.settings import USER_POINTS_MAX_LINES  # noqa: E402
from naturametrics.services.user_points import (  # noqa: E402
    EXAMPLE_TEXT, parse_coordinate_text,
)


def test_example_text_itself_parses_cleanly():
    """If EXAMPLE_TEXT is ever edited, it must stay a paste-ready template —
    the UI shows it verbatim as "the format", not as a description of one."""
    result = parse_coordinate_text(EXAMPLE_TEXT)
    assert len(result.points) == 2
    assert result.errors == []


def test_named_point_uses_the_given_name_as_id():
    result = parse_coordinate_text("Fazenda X, -9.5, -63.0")
    assert result.points == [{"id": "Fazenda X", "lat": -9.5, "lon": -63.0}]


def test_unnamed_point_gets_an_auto_id_from_its_line_number():
    result = parse_coordinate_text("-9.5, -63.0")
    assert result.points[0]["id"] == "P1"


def test_comments_and_blank_lines_are_skipped_silently():
    result = parse_coordinate_text("# a header\n\n-9.5, -63.0\n\n# another\n")
    assert len(result.points) == 1
    assert result.errors == []


def test_unparseable_line_is_reported_not_dropped_silently():
    result = parse_coordinate_text("not a coordinate at all here")
    assert result.points == []
    assert len(result.errors) == 1
    assert "linha 1" in result.errors[0]


def test_out_of_range_coordinates_are_rejected():
    result = parse_coordinate_text("P, 999, -63.0")
    assert result.points == []
    assert "fora do intervalo" in result.errors[0]


def test_out_of_brazil_point_is_kept_but_flagged():
    """Kept on the map — only the Earth Engine analysis refuses it later, with
    the same message a stray map click already gets (services.geo)."""
    result = parse_coordinate_text("Paris, 48.85, 2.35")
    assert len(result.points) == 1
    assert result.points[0]["id"] == "Paris"
    assert any("fora do Brasil" in e for e in result.errors)


def test_duplicate_names_are_disambiguated():
    result = parse_coordinate_text("A, -9.5, -63.0\nA, -10.0, -64.0")
    ids = [p["id"] for p in result.points]
    assert len(ids) == len(set(ids)) == 2


def test_whitespace_only_line_still_parses():
    result = parse_coordinate_text("-9.5   -63.0")
    assert result.points == [{"id": "P1", "lat": -9.5, "lon": -63.0}]


def test_truncates_at_the_cap_and_says_so():
    lines = "\n".join(f"-9.{i}, -63.0" for i in range(USER_POINTS_MAX_LINES + 5))
    result = parse_coordinate_text(lines)
    assert len(result.points) == USER_POINTS_MAX_LINES
    assert result.truncated is True
    assert result.total_valid_lines == USER_POINTS_MAX_LINES + 5


def test_under_the_cap_is_not_truncated():
    result = parse_coordinate_text("-9.5, -63.0\n-10.0, -64.0")
    assert result.truncated is False


# --------------------------------------------------------------------------- #
# SelectionSpec — the branch that reuses the conglomerado export pipeline
# --------------------------------------------------------------------------- #

def test_selection_spec_prefers_user_points_over_manual_conglomerados():
    from naturametrics.services.exports import SelectionSpec

    spec = SelectionSpec(
        conglomerados=["MT_1"],
        user_points=[{"id": "A", "lat": -9.5, "lon": -63.0}],
    )
    assert spec.is_user_points is True
    assert spec.is_manual is False  # user_points wins, per is_manual's own guard


def test_selection_spec_user_points_shape_matches_conglomerado_points():
    """Every downstream fan-out reads row["conglomerado"]/["uf"]/["municipio"]/
    ["bioma"]/["lat"]/["lon"] regardless of source — this is the contract that
    lets selection_buffer_frame etc. not know or care which kind of selection
    they were handed."""
    from naturametrics.services.exports import SelectionSpec

    spec = SelectionSpec(user_points=[{"id": "A", "lat": -9.5, "lon": -63.0}])
    [row] = spec.points()
    assert set(row) == {"ponto_id", "conglomerado", "regiao", "uf",
                        "municipio", "bioma", "lon", "lat"}
    assert row["conglomerado"] == "A"
    assert row["uf"] == row["municipio"] == row["bioma"] == row["regiao"] == ""


def test_selection_spec_user_points_filter_label_names_the_count():
    from naturametrics.services.exports import SelectionSpec

    spec = SelectionSpec(user_points=[{"id": "A", "lat": -9.5, "lon": -63.0}] * 3)
    assert "3" in spec.filter_label()


@pytest.mark.ee
def test_selection_pixel_frame_works_for_a_user_points_spec():
    from naturametrics.services.exports import SelectionSpec, selection_pixel_frame

    try:
        from naturametrics.services.ee_client import initialize_earth_engine
        initialize_earth_engine()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Earth Engine unavailable: {exc}")

    spec = SelectionSpec(user_points=[
        {"id": "A", "lat": -9.5, "lon": -63.0},
        {"id": "B", "lat": -11.0, "lon": -55.0},
    ])
    df, prov = selection_pixel_frame(spec)
    assert len(df) == 2
    assert set(df["conglomerado"]) == {"A", "B"}
    assert (df["uf"] == "").all()
    assert prov.name == "selection_point_pixel"
