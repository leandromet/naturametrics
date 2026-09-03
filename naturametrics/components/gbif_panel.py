"""The GBIF biodiversity panel — the sidebar's "busca avançada".

Modelled on the advanced search of the SiBBr ALA-hub
(https://ala-hub.sibbr.gov.br/ala-hub/search#tab_advanceSearch), which is the
Brazilian GBIF node running the same occurrence data this layer draws. That form
is three blocks — a full-text box, a set of taxon pickers, and a set of
"records that specify the following fields" constraints — and this panel keeps
that division because it is the division a user of the national node already
knows.

What it deliberately does NOT copy is the flat 20-field layout: this lives in a
~320 px sidebar next to a map, not on a full-width search page, so the same
fields are stacked into collapsible sub-accordions and the two that most change
what appears on screen — the taxonomy and the record type — are the ones on top.

Kept out of components/layer_panel.py, which is already 1 167 lines, and given
its own sidebar group rather than being folded into the IFN/IBAMA one: those
three sources are all *ground records of enforcement or inventory*, and
biodiversity occurrences are a different kind of thing entirely.
"""

from __future__ import annotations

import reflex as rx

from ..config import gbif as gc
from ..state import AppState
from .layer_panel import _filter_select, _info_icon, _section

#: The blank option every dropdown carries. Must match state/_gbif.py::_ANY —
#: rx.select cannot hold "" as a real value, so "no filter" needs a sentinel.
_ANY = "—"


def _taxon_level(label, options, value, on_change) -> rx.Component:
    """One rank of the cascade. Hidden entirely when it has no options yet:
    an empty dropdown below an unselected parent is noise, and the backbone is
    not rank-complete — some branches genuinely skip a level, and a permanently
    empty "Ordem" box would read as a bug rather than as the truth."""
    return rx.cond(
        options.length() > 1,
        _filter_select(label, options, value, on_change),
        rx.fragment(),
    )


def _taxonomy_block() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(AppState.tr["gbif_taxonomy_title"], size="1",
                    color_scheme="gray", weight="medium"),
            rx.spacer(),
            rx.cond(AppState.gbif_taxa_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center",
        ),
        _filter_select(AppState.tr["gbif_rank_kingdom"],
                       AppState.gbif_kingdom_options,
                       rx.cond(AppState.gbif_kingdom == "", _ANY,
                               AppState.gbif_kingdom),
                       AppState.set_gbif_kingdom),
        _taxon_level(AppState.tr["gbif_rank_phylum"],
                     AppState.gbif_phylum_options,
                     rx.cond(AppState.gbif_phylum == "", _ANY,
                             AppState.gbif_phylum),
                     AppState.set_gbif_phylum),
        _taxon_level(AppState.tr["gbif_rank_class"],
                     AppState.gbif_class__options,
                     rx.cond(AppState.gbif_class_ == "", _ANY,
                             AppState.gbif_class_),
                     AppState.set_gbif_class),
        _taxon_level(AppState.tr["gbif_rank_order"],
                     AppState.gbif_order_options,
                     rx.cond(AppState.gbif_order == "", _ANY,
                             AppState.gbif_order),
                     AppState.set_gbif_order),
        _taxon_level(AppState.tr["gbif_rank_family"],
                     AppState.gbif_family_options,
                     rx.cond(AppState.gbif_family == "", _ANY,
                             AppState.gbif_family),
                     AppState.set_gbif_family),
        _taxon_level(AppState.tr["gbif_rank_genus"],
                     AppState.gbif_genus_options,
                     rx.cond(AppState.gbif_genus == "", _ANY,
                             AppState.gbif_genus),
                     AppState.set_gbif_genus),
        _taxon_level(AppState.tr["gbif_rank_species"],
                     AppState.gbif_species_options,
                     rx.cond(AppState.gbif_species == "", _ANY,
                             AppState.gbif_species),
                     AppState.set_gbif_species),
        spacing="2", width="100%",
    )


def _name_block() -> rx.Component:
    """Free-text scientific-name search with backbone autocomplete.

    The ALA form's own "Species/Taxon" box, and the fast path past the cascade:
    someone who already knows they want *Panthera onca* should not have to walk
    Animalia → Chordata → Mammalia → Carnivora → Felidae to say so.

    Each suggestion shows its higher taxon, which is not decoration — GBIF's
    backbone is full of homonyms, and "Panthera" is both a cat genus (Felidae)
    and a moth genus (Geometridae). Without the context line the two are
    indistinguishable in the list.
    """
    return rx.vstack(
        rx.text(AppState.tr["gbif_name_label"], size="1", color_scheme="gray"),
        rx.hstack(
            rx.input(
                value=AppState.gbif_name_query,
                on_change=AppState.set_gbif_name_query,
                placeholder=AppState.tr["gbif_name_placeholder"],
                size="2", width="100%",
            ),
            rx.cond(AppState.gbif_name_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.gbif_name_suggestions.length() > 0,
            rx.vstack(
                rx.foreach(
                    AppState.gbif_name_suggestions,
                    lambda s: rx.button(
                        rx.vstack(
                            rx.text(s["name"], size="1", weight="medium"),
                            rx.text(f"{s['rank']} · {s['context']}", size="1",
                                    color_scheme="gray"),
                            spacing="0", align_items="start",
                        ),
                        variant="ghost", size="1", width="100%",
                        justify="start",
                        on_click=AppState.choose_gbif_suggestion(
                            s["key"], s["name"]),
                    ),
                ),
                spacing="1", width="100%",
                style={"maxHeight": "180px", "overflowY": "auto"},
            ),
            rx.fragment(),
        ),
        spacing="1", width="100%", align_items="stretch",
    )


def _record_block() -> rx.Component:
    """Basis of record, year range, UF — the ALA form's "records that specify
    the following fields" block, minus the fields that need a full-width page
    (catalogue number, institution, collector)."""
    return rx.vstack(
        rx.text(AppState.tr["gbif_basis_label"], size="1", color_scheme="gray"),
        rx.vstack(
            *[
                rx.hstack(
                    rx.checkbox(
                        checked=AppState.gbif_basis.contains(code),
                        on_change=lambda checked, c=code:
                            AppState.toggle_gbif_basis(c, checked),
                        size="1",
                    ),
                    rx.text(
                        rx.cond(AppState.language == "pt", label_pt, label_en),
                        size="1",
                    ),
                    spacing="2", align="center", width="100%",
                )
                # Only the five commonest: the remaining four account for well
                # under 1 % of Brazilian records between them, and nine
                # checkboxes in a 320 px sidebar is a wall.
                for code, label_pt, label_en in gc.BASIS_OF_RECORD[:5]
            ],
            spacing="1", width="100%",
        ),
        rx.divider(),
        rx.hstack(
            rx.text(AppState.tr["gbif_year_label"], size="1", color_scheme="gray"),
            rx.spacer(),
            rx.text(AppState.gbif_year_label, size="1"),
            width="100%",
        ),
        rx.slider(
            min=gc.YEAR_MIN, max=2026, step=1,
            default_value=[gc.YEAR_MIN, 2026],
            on_value_commit=AppState.set_gbif_years,
            width="100%",
        ),
        rx.divider(),
        _filter_select(AppState.tr["gbif_uf_label"], AppState.gbif_uf_options,
                       AppState.gbif_uf_value, AppState.set_gbif_uf),
        spacing="2", width="100%",
    )


def _sub_accordion(value: str, title, icon: str, body: rx.Component,
                   default_open: bool = False) -> rx.Component:
    return rx.accordion.root(
        rx.accordion.item(
            rx.accordion.header(
                rx.accordion.trigger(
                    rx.hstack(
                        rx.icon(icon, size=13),
                        rx.text(title, size="2", weight="medium"),
                        spacing="2", align="center",
                    ),
                ),
            ),
            rx.accordion.content(
                rx.box(body, padding_top="0.35rem"),
                padding_x="0",
            ),
            value=value,
        ),
        type="single", collapsible=True, variant="ghost", width="100%",
        **({"default_value": value} if default_open else {}),
    )


def gbif_control() -> rx.Component:
    """The layer toggle, the zoom gate, the honesty line, and the search."""
    return _section(
        AppState.tr["section_gbif"],
        rx.hstack(
            rx.switch(checked=AppState.show_gbif, on_change=AppState.toggle_gbif),
            rx.text(AppState.tr["gbif_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_gbif,
            rx.vstack(
                # The zoom gate, stated rather than left to be discovered. Below
                # zoom 10 the layer is removed entirely by leaflet_map.js, so
                # without this the switch looks broken at country view.
                rx.callout(
                    AppState.tr["gbif_zoom_note"],
                    icon="zoom-in", size="1", color_scheme="blue", width="100%",
                ),
                # "300 / 22 400 nesta vista". Shown only when the fetch was
                # genuinely truncated — see GbifMixin.gbif_view_label.
                rx.cond(
                    AppState.gbif_view_label != "",
                    rx.hstack(
                        rx.badge(AppState.gbif_view_label, color_scheme="amber",
                                 variant="soft"),
                        rx.text(AppState.tr["gbif_truncated_note"], size="1",
                                color_scheme="gray"),
                        spacing="2", align="center", width="100%",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    AppState.gbif_layer_error != "",
                    rx.callout(AppState.gbif_layer_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.fragment(),
                ),
                _sub_accordion("gbif_taxonomy", AppState.tr["gbif_taxonomy_group"],
                               "git-branch",
                               rx.vstack(_name_block(), rx.divider(),
                                         _taxonomy_block(), spacing="3",
                                         width="100%"),
                               default_open=True),
                _sub_accordion("gbif_records", AppState.tr["gbif_records_group"],
                               "list-filter", _record_block()),
                rx.hstack(
                    rx.cond(
                        AppState.gbif_taxon_label != "",
                        rx.badge(AppState.gbif_taxon_label, color_scheme="jade",
                                 variant="soft"),
                        rx.fragment(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        AppState.gbif_has_filter,
                        rx.button(
                            rx.icon("rotate-ccw", size=12),
                            AppState.tr["clear_button"],
                            size="1", variant="ghost",
                            on_click=AppState.clear_gbif_filters,
                        ),
                        rx.fragment(),
                    ),
                    width="100%", align="center",
                ),
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1",
                            color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.gbif_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(min=0, max=100, step=5, default_value=[85],
                          on_change=AppState.set_gbif_opacity, width="100%"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["gbif_info"],
    )


# --------------------------------------------------------------------------- #
# The analysis tab
# --------------------------------------------------------------------------- #
# Lives here rather than in components/results.py so that everything reading
# the GBIF state stays in one file, but it is rendered as the fifth tab of
# ``results.py::_forest_age_panel`` — a species list is a RESULT about the
# study point, the same kind of thing as the age and biomass tabs, not a
# control over what the map draws. It also simply needs the width: a table of
# species names and counts is unreadable in a 320 px sidebar.


def _kingdom_chips(row) -> rx.Component:
    return rx.hstack(
        rx.foreach(
            row.kingdoms,
            lambda k: rx.badge(f"{k.name} · {k.count}", size="1",
                               variant="soft", color_scheme="gray"),
        ),
        spacing="1", wrap="wrap",
    )


def _buffer_card(row) -> rx.Component:
    """One radius: the totals, the kingdom split, and its species table."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(row.radius_label, color_scheme="jade", variant="solid",
                         size="2"),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon("locate-fixed", size=14),
                        size="1", variant="soft", color_scheme="jade",
                        on_click=AppState.show_gbif_zone(row.radius_km),
                    ),
                    content=AppState.tr["gbif_show_zone_hint"],
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text(row.total_label, size="3", weight="bold"),
                    rx.text(AppState.tr["gbif_records_word"], size="1",
                            color_scheme="gray"),
                    spacing="0", align_items="end",
                ),
                rx.vstack(
                    rx.text(row.richness_label, size="3", weight="bold"),
                    rx.text(AppState.tr["gbif_species_word"], size="1",
                            color_scheme="gray"),
                    spacing="0", align_items="end",
                ),
                width="100%", align="center", spacing="4",
            ),
            _kingdom_chips(row),
            rx.cond(
                row.species_top.length() > 0,
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell(
                                    AppState.tr["gbif_col_species"]),
                                rx.table.column_header_cell(
                                    AppState.tr["gbif_col_records"],
                                    style={"textAlign": "right"}),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                row.species_top,
                                lambda sp: rx.table.row(
                                    rx.table.cell(
                                        rx.text(sp.name, size="1",
                                                style={"fontStyle": "italic"})),
                                    rx.table.cell(
                                        rx.text(sp.count_label, size="1"),
                                        style={"textAlign": "right"}),
                                ),
                            ),
                        ),
                        size="1", variant="ghost", width="100%",
                    ),
                    type="auto", scrollbars="vertical",
                    style={"maxHeight": "260px"},
                ),
                rx.text(AppState.tr["gbif_buffers_empty"], size="1",
                        color_scheme="gray"),
            ),
            spacing="2", width="100%", align_items="stretch",
        ),
        width="100%",
    )


def gbif_buffer_panel() -> rx.Component:
    """The "Espécies (GBIF)" analysis tab.

    Run on demand rather than with the rest of the analysis: it is five
    requests to a third party, and someone who came for the land-cover history
    should not pay for them on every map click. Turns the map layer on if it
    was off (state/_gbif.py::run_gbif_buffers) — counting species while the
    dots themselves stay hidden was confusing enough on its own to report as
    a bug — but does not force it back off, so the layer can still be
    switched off afterward for just the counts.
    """
    return rx.vstack(
        rx.cond(
            AppState.has_point,
            rx.vstack(
                rx.hstack(
                    rx.button(
                        rx.icon("sprout", size=14),
                        AppState.tr["gbif_buffers_run"],
                        size="2", variant="soft", color_scheme="jade",
                        on_click=AppState.run_gbif_buffers,
                        loading=AppState.gbif_buffer_busy,
                    ),
                    rx.cond(
                        AppState.gbif_taxon_label != "",
                        rx.badge(AppState.gbif_taxon_label, color_scheme="jade",
                                 variant="soft", size="2"),
                        rx.fragment(),
                    ),
                    rx.spacer(),
                    # Only once there is something to export — two dead
                    # buttons beside a "list species" call to action read as
                    # broken rather than as not-yet-applicable.
                    rx.cond(
                        AppState.gbif_buffer_rows.length() > 0,
                        rx.hstack(
                            rx.tooltip(
                                rx.button(
                                    rx.icon("table", size=14), "ODS",
                                    size="1", variant="soft", color_scheme="gray",
                                    on_click=AppState.download_gbif_species_ods,
                                ),
                                content=AppState.tr["gbif_export_ods_hint"],
                            ),
                            rx.tooltip(
                                rx.button(
                                    rx.icon("download", size=14), "CSV",
                                    size="1", variant="soft", color_scheme="gray",
                                    on_click=AppState.download_gbif_species_csv,
                                ),
                                content=AppState.tr["gbif_export_csv_hint"],
                            ),
                            spacing="2", align="center",
                        ),
                        rx.fragment(),
                    ),
                    rx.text(AppState.tr["gbif_buffers_note"], size="1",
                            color_scheme="gray"),
                    width="100%", align="center", spacing="3", wrap="wrap",
                ),
                rx.cond(
                    AppState.gbif_export_error != "",
                    rx.callout(AppState.gbif_export_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.fragment(),
                ),
                rx.cond(
                    AppState.gbif_buffer_error != "",
                    rx.callout(AppState.gbif_buffer_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.fragment(),
                ),
                rx.cond(
                    AppState.gbif_buffer_rows.length() > 0,
                    rx.grid(
                        rx.foreach(AppState.gbif_buffer_rows, _buffer_card),
                        # rx.grid's `columns` takes a string or an
                        # rx.breakpoints object, NOT the plain responsive list
                        # every other prop in this app accepts — passing a list
                        # fails the page build (tests/test_app_builds.py).
                        # One card per row on a phone; two from tablet up,
                        # which is where a species table stops being cramped.
                        columns=rx.breakpoints(initial="1", md="2"),
                        spacing="3", width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing="3", width="100%", align_items="stretch",
            ),
            rx.callout(AppState.tr["gbif_buffers_no_point"], icon="info",
                       size="1", color_scheme="gray", width="100%"),
        ),
        width="100%", spacing="3", align_items="stretch",
    )
