"""The quick-start card: what a first-time visitor reads in 30 seconds.

Four numbered steps and a closing line pointing at the full "how to use"
guide — nothing that needs scrolling on a desktop, and nothing that teaches a
feature the first visit does not need. It floats over the map's right edge
on a desktop and across the top of the map on a phone (above the bottom
sheet, which keeps the controls), and it is dismissed for good with either
button: the "seen" flag lives in the viewer's own browser storage
(``quickstart_seen``), so it never follows a user to another screen and never
reaches the server's idea of state.

Written once and shared verbatim across the suite's pages (Camposcope and
Naturametrics, Brazil and Canada; Yvynation) — each page passes its own state
class, accent colour and the breakpoint its layout switches at. The state
class must provide ``tr`` (with the ``qs_*`` keys), ``show_quickstart``,
``dismiss_quickstart`` and ``open_full_howto``.

Gated on ``is_hydrated`` as well as ``show_quickstart``: before hydration the
storage-backed flag still holds its default, and a returning visitor would see
the card flash for a moment before it learned it had been dismissed.
"""

from __future__ import annotations

import reflex as rx

#: Mobile layout up to (not including) this Radix breakpoint index — 2 = "md"
#: (768px), 3 = "lg" (1024px). Must match where the page swaps its sidebar for
#: a bottom sheet, or the card lands on the wrong side of it.
def _responsive(mobile, desktop, desktop_from: int) -> list:
    return [mobile] * desktop_from + [desktop] * (4 - desktop_from)


#: Radix breakpoint names for the list indices ``_responsive`` uses.
_BP_NAME = {1: "xs", 2: "sm", 3: "md"}


def _bp(mobile, desktop, desktop_from: int):
    """The same split for a *typed* prop (``size``, ``spacing``): those
    reject a plain list at build time and need ``rx.breakpoints``."""
    return rx.breakpoints(initial=mobile, **{_BP_NAME[desktop_from]: desktop})


def _step(S, n: int, accent: str, desktop_from: int) -> rx.Component:
    return rx.hstack(
        rx.box(
            rx.text(str(n), size="1", weight="bold", color="white"),
            background=f"var(--{accent}-9)",
            border_radius="50%",
            width="20px", height="20px", min_width="20px",
            display="flex", align_items="center", justify_content="center",
            margin_top="1px",
        ),
        rx.text(
            rx.text.strong(S.tr[f"qs_step{n}_lead"]),
            " ",
            S.tr[f"qs_step{n}_body"],
            # One size down on a phone: at 390px the card at desktop sizes
            # ran past the space above the sheet and scrolled its own two
            # buttons — the hand-off to the full guide — out of view.
            size=_bp("1", "2", desktop_from),
        ),
        spacing="2",
        align="start",
        width="100%",
    )


def quickstart_card(S, *, accent: str, desktop_from: int = 2, steps: int = 4,
                    mobile_max_height: str = "calc(100% - 45vh - 16px)",
                    ) -> rx.Component:
    """The card, positioned for a ``position: relative`` map container.

    ``mobile_max_height``'s default suits a map box that a 45vh bottom sheet
    covers from below; a page whose phone map is its own short box (no sheet
    over it) passes ``"calc(100% - 16px)"``.
    """
    tr = S.tr
    card = rx.vstack(
        rx.hstack(
            rx.icon("rocket", size=16, color=f"var(--{accent}-11)",
                    flex_shrink="0"),
            rx.text(tr["qs_title"], size="3", weight="bold"),
            rx.spacer(),
            rx.icon_button(
                rx.icon("x", size=14),
                on_click=S.dismiss_quickstart,
                size="1", variant="ghost", color_scheme="gray",
                aria_label=tr["qs_close_aria"],
            ),
            width="100%",
            align="center",
            spacing="2",
        ),
        *[_step(S, i, accent, desktop_from) for i in range(1, steps + 1)],
        rx.text(tr["qs_more"], size="1", color="var(--gray-11)"),
        rx.hstack(
            rx.button(
                tr["qs_full_howto"],
                rx.icon("arrow-right", size=14),
                on_click=S.open_full_howto,
                size="1", variant="soft", color_scheme=accent,
            ),
            rx.spacer(),
            rx.button(
                tr["qs_got_it"],
                on_click=S.dismiss_quickstart,
                size="1", color_scheme=accent,
            ),
            width="100%",
            align="center",
            wrap="wrap",
            spacing="2",
        ),
        role="region",
        aria_label=tr["qs_title"],
        spacing=_bp("2", "3", desktop_from),
        # NOT rx.vstack's default align="start", which would size every row to
        # its own content and let a long line push the card past a phone's
        # width — see the sibling apps' mobile-sheet fix for the measured case.
        align="stretch",
        position="absolute",
        top=_responsive("8px", "12px", desktop_from),
        right=_responsive("8px", "12px", desktop_from),
        # 54px on a phone clears Leaflet's zoom/fullscreen column (top-left,
        # z-index 1000 — above this card, which has to stay below the sheet
        # at 1000 too, so it moves aside rather than over).
        left=_responsive("54px", "auto", desktop_from),
        width=_responsive("auto", "330px", desktop_from),
        # A phone keeps its bottom 45vh for the sheet; the card must end above
        # it rather than slide underneath.
        max_height=_responsive(mobile_max_height, "calc(100% - 24px)",
                               desktop_from),
        overflow_y="auto",
        padding=_responsive("10px 12px", "14px 16px", desktop_from),
        background="var(--color-panel-solid)",
        border="1px solid var(--gray-5)",
        border_radius="var(--radius-4)",
        box_shadow="0 6px 24px rgba(0, 0, 0, 0.22)",
        # Above Leaflet's panes (~700) and the on-map legend (900), below the
        # results drawer / bottom sheet (1000) — dragging the sheet up must
        # cover the card, not hide under it.
        z_index="990",
    )
    return rx.cond(S.is_hydrated & S.show_quickstart, card)
