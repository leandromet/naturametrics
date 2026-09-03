"""The GBIF biodiversity panel — the Canada page's sidebar advanced search.

Ported from the Brazil page's ``components/gbif_panel.py`` feature-for-feature
(same ALA-hub-style three-block layout: full-text box, taxon pickers, "records
that specify the following fields") — see that file's docstring for the design
rationale, none of which is country-specific. Only the state root (``S`` =
``CanadaState``), the GADM table (``PROVINCE_GADM`` instead of ``UF_GADM``) and
the "state" → "province/territory" wording differ.

Mounted into ``layer_panel()`` the same way as the Brazil page: this module
imports ``_section``/``_info_icon``/``_filter_select`` back from
``layer_panel.py``, so ``layer_panel()`` imports ``gbif_control`` from here
lazily, inside its own function body, to avoid the circular top-level import.
"""

from __future__ import annotations

import reflex as rx

from ..config import gbif as gc
from ..state import CanadaState as S
from .layer_panel import _filter_select, _info_icon, _section

_ANY = "—"


def _taxon_level(label, options, value, on_change) -> rx.Component:
    return rx.cond(
        options.length() > 1,
        _filter_select(label, options, value, on_change),
        rx.fragment(),
    )


def _taxonomy_block() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(S.tr["gbif_taxonomy_title"], size="1",
                    color_scheme="gray", weight="medium"),
            rx.spacer(),
            rx.cond(S.gbif_taxa_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center",
        ),
        _filter_select(S.tr["gbif_rank_kingdom"],
                       S.gbif_kingdom_options,
                       rx.cond(S.gbif_kingdom == "", _ANY, S.gbif_kingdom),
                       S.set_gbif_kingdom),
        _taxon_level(S.tr["gbif_rank_phylum"], S.gbif_phylum_options,
                     rx.cond(S.gbif_phylum == "", _ANY, S.gbif_phylum),
                     S.set_gbif_phylum),
        _taxon_level(S.tr["gbif_rank_class"], S.gbif_class__options,
                     rx.cond(S.gbif_class_ == "", _ANY, S.gbif_class_),
                     S.set_gbif_class),
        _taxon_level(S.tr["gbif_rank_order"], S.gbif_order_options,
                     rx.cond(S.gbif_order == "", _ANY, S.gbif_order),
                     S.set_gbif_order),
        _taxon_level(S.tr["gbif_rank_family"], S.gbif_family_options,
                     rx.cond(S.gbif_family == "", _ANY, S.gbif_family),
                     S.set_gbif_family),
        _taxon_level(S.tr["gbif_rank_genus"], S.gbif_genus_options,
                     rx.cond(S.gbif_genus == "", _ANY, S.gbif_genus),
                     S.set_gbif_genus),
        _taxon_level(S.tr["gbif_rank_species"], S.gbif_species_options,
                     rx.cond(S.gbif_species == "", _ANY, S.gbif_species),
                     S.set_gbif_species),
        spacing="2", width="100%",
    )


def _name_block() -> rx.Component:
    return rx.vstack(
        rx.text(S.tr["gbif_name_label"], size="1", color_scheme="gray"),
        rx.hstack(
            rx.input(
                value=S.gbif_name_query,
                on_change=S.set_gbif_name_query,
                placeholder=S.tr["gbif_name_placeholder"],
                size="2", width="100%",
            ),
            rx.cond(S.gbif_name_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            S.gbif_name_suggestions.length() > 0,
            rx.vstack(
                rx.foreach(
                    S.gbif_name_suggestions,
                    lambda s: rx.button(
                        rx.vstack(
                            rx.text(s["name"], size="1", weight="medium"),
                            rx.text(f"{s['rank']} · {s['context']}", size="1",
                                    color_scheme="gray"),
                            spacing="0", align_items="start",
                        ),
                        variant="ghost", size="1", width="100%",
                        justify="start",
                        on_click=S.choose_gbif_suggestion(s["key"], s["name"]),
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
    return rx.vstack(
        rx.text(S.tr["gbif_basis_label"], size="1", color_scheme="gray"),
        rx.vstack(
            *[
                rx.hstack(
                    rx.checkbox(
                        checked=S.gbif_basis.contains(code),
                        on_change=lambda checked, c=code:
                            S.toggle_gbif_basis(c, checked),
                        size="1",
                    ),
                    rx.text(label_en, size="1"),
                    spacing="2", align="center", width="100%",
                )
                # Only the five commonest: checked live against Canadian
                # records (canada/config/gbif.py), the remaining four still
                # account for well under 1% between them.
                for code, _label_pt, label_en in gc.BASIS_OF_RECORD[:5]
            ],
            spacing="1", width="100%",
        ),
        rx.divider(),
        rx.hstack(
            rx.text(S.tr["gbif_year_label"], size="1", color_scheme="gray"),
            rx.spacer(),
            rx.text(S.gbif_year_label, size="1"),
            width="100%",
        ),
        rx.slider(
            min=gc.YEAR_MIN, max=2026, step=1,
            default_value=[gc.YEAR_MIN, 2026],
            on_value_commit=S.set_gbif_years,
            width="100%",
        ),
        rx.divider(),
        _filter_select(S.tr["gbif_province_label"], S.gbif_province_options,
                       S.gbif_province_value, S.set_gbif_province),
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
        S.tr["section_gbif"],
        rx.hstack(
            rx.switch(checked=S.show_gbif, on_change=S.toggle_gbif),
            rx.text(S.tr["gbif_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            S.show_gbif,
            rx.vstack(
                rx.callout(
                    S.tr["gbif_zoom_note"],
                    icon="zoom-in", size="1", color_scheme="blue", width="100%",
                ),
                rx.cond(
                    S.gbif_view_label != "",
                    rx.hstack(
                        rx.badge(S.gbif_view_label, color_scheme="amber",
                                 variant="soft"),
                        rx.text(S.tr["gbif_truncated_note"], size="1",
                                color_scheme="gray"),
                        spacing="2", align="center", width="100%",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    S.gbif_layer_error != "",
                    rx.callout(S.gbif_layer_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.fragment(),
                ),
                _sub_accordion("gbif_taxonomy", S.tr["gbif_taxonomy_group"],
                               "git-branch",
                               rx.vstack(_name_block(), rx.divider(),
                                         _taxonomy_block(), spacing="3",
                                         width="100%"),
                               default_open=True),
                _sub_accordion("gbif_records", S.tr["gbif_records_group"],
                               "list-filter", _record_block()),
                rx.hstack(
                    rx.cond(
                        S.gbif_taxon_label != "",
                        rx.badge(S.gbif_taxon_label, color_scheme="jade",
                                 variant="soft"),
                        rx.fragment(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        S.gbif_has_filter,
                        rx.button(
                            rx.icon("rotate-ccw", size=12),
                            S.tr["clear_button"],
                            size="1", variant="ghost",
                            on_click=S.clear_gbif_filters,
                        ),
                        rx.fragment(),
                    ),
                    width="100%", align="center",
                ),
                rx.hstack(
                    rx.text(S.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(S.gbif_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(min=0, max=100, step=5, default_value=[85],
                          on_change=S.set_gbif_opacity, width="100%"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=S.tr["gbif_info"],
    )


# --------------------------------------------------------------------------- #
# The analysis panel
# --------------------------------------------------------------------------- #
# Rendered by components/results.py, not layer_panel.py — see that file's own
# comment: this is a RESULT about the study point, the same kind of thing as
# the crop-inventory and forest panels beside it, not a control over what the
# map draws, and it needs the results area's width to show a species table.


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
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(row.radius_label, color_scheme="jade", variant="solid",
                         size="2"),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon("locate-fixed", size=14),
                        size="1", variant="soft", color_scheme="jade",
                        on_click=S.show_gbif_zone(row.radius_km),
                    ),
                    content=S.tr["gbif_show_zone_hint"],
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text(row.total_label, size="3", weight="bold"),
                    rx.text(S.tr["gbif_records_word"], size="1",
                            color_scheme="gray"),
                    spacing="0", align_items="end",
                ),
                rx.vstack(
                    rx.text(row.richness_label, size="3", weight="bold"),
                    rx.text(S.tr["gbif_species_word"], size="1",
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
                                    S.tr["gbif_col_species"]),
                                rx.table.column_header_cell(
                                    S.tr["gbif_col_records"],
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
                rx.text(S.tr["gbif_buffers_empty"], size="1", color_scheme="gray"),
            ),
            spacing="2", width="100%", align_items="stretch",
        ),
        width="100%",
    )


def gbif_buffer_panel() -> rx.Component:
    """The species-in-buffers analysis, run on demand — same reasoning as the
    Brazil page: five requests to a third party that someone who came for the
    crop-inventory history should not pay for automatically."""
    return rx.vstack(
        rx.cond(
            S.has_point,
            rx.vstack(
                rx.hstack(
                    rx.button(
                        rx.icon("sprout", size=14),
                        S.tr["gbif_buffers_run"],
                        size="2", variant="soft", color_scheme="jade",
                        on_click=S.run_gbif_buffers,
                        loading=S.gbif_buffer_busy,
                    ),
                    rx.cond(
                        S.gbif_taxon_label != "",
                        rx.badge(S.gbif_taxon_label, color_scheme="jade",
                                 variant="soft", size="2"),
                        rx.fragment(),
                    ),
                    rx.spacer(),
                    rx.cond(
                        S.gbif_buffer_rows.length() > 0,
                        rx.hstack(
                            rx.tooltip(
                                rx.button(
                                    rx.icon("table", size=14), "ODS",
                                    size="1", variant="soft", color_scheme="gray",
                                    on_click=S.download_gbif_species_ods,
                                ),
                                content=S.tr["gbif_export_ods_hint"],
                            ),
                            rx.tooltip(
                                rx.button(
                                    rx.icon("download", size=14), "CSV",
                                    size="1", variant="soft", color_scheme="gray",
                                    on_click=S.download_gbif_species_csv,
                                ),
                                content=S.tr["gbif_export_csv_hint"],
                            ),
                            spacing="2", align="center",
                        ),
                        rx.fragment(),
                    ),
                    rx.text(S.tr["gbif_buffers_note"], size="1", color_scheme="gray"),
                    width="100%", align="center", spacing="3", wrap="wrap",
                ),
                rx.cond(
                    S.gbif_export_error != "",
                    rx.callout(S.gbif_export_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.fragment(),
                ),
                rx.cond(
                    S.gbif_buffer_error != "",
                    rx.callout(S.gbif_buffer_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.fragment(),
                ),
                rx.cond(
                    S.gbif_buffer_rows.length() > 0,
                    rx.grid(
                        rx.foreach(S.gbif_buffer_rows, _buffer_card),
                        columns=rx.breakpoints(initial="1", md="2"),
                        spacing="3", width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing="3", width="100%", align_items="stretch",
            ),
            rx.callout(S.tr["gbif_buffers_no_point"], icon="info",
                       size="1", color_scheme="gray", width="100%"),
        ),
        width="100%", spacing="3", align_items="stretch",
    )
