"""UI chrome state: language, panel visibility."""

from __future__ import annotations

import reflex as rx

from ..config import settings as st
from ..translations import get_translations


class UIMixin(rx.State, mixin=True):
    """Presentation state with no analytical meaning."""

    language: str = st.DEFAULT_LANGUAGE
    #: Controls the MOBILE overlay drawer only — the desktop sidebar is
    #: always visible. Starts closed so the map is the first thing seen.
    sidebar_open: bool = False

    #: The on-map legend (components/map_legend.py) collapsed to just its
    #: header. Open by default; `adopt_viewport` closes it on a narrow screen.
    legend_open: bool = True
    #: Whether `adopt_viewport` has already run this session. The legend is
    #: conditionally rendered, so its `on_mount` fires again on every remount
    #: — without this guard a phone user who opened the legend would have it
    #: snap shut again on the next re-render.
    _viewport_adopted: bool = False

    #: The header's three info dialogs, each fully controlled. Not decorative:
    #: rx.dialog.close's Radix "asChild" prop-cloning silently fails to reach a
    #: button that Reflex has extracted into its own standalone helper
    #: component (which every button used only as Dialog.Close's child is,
    #: regardless of whether it happens to be identical elsewhere) — the
    #: extracted function never receives the onClick Radix tries to inject, so
    #: the close button renders but does nothing, and only Escape/overlay-click
    #: (which go through Radix's own document-level listeners, not this prop)
    #: still close the dialog. Driving open/close from state sidesteps the
    #: mechanism entirely rather than fighting the compiler's extraction choice.
    como_usar_open: bool = False
    como_citar_open: bool = False
    ai_disclaimer_open: bool = False

    #: Which of `_all_groups()`'s accordion groups are open (components/
    #: layer_panel.py) — controlled so the backend can force one open, not
    #: just so the user can toggle them; see `_open_study_area`.
    open_groups: list[str] = []
    #: Whether `_open_study_area` has already fired this session — same
    #: one-shot guard as `_viewport_adopted` above, and for the same reason:
    #: only the FIRST analysis area should force the group open, so a user
    #: who deliberately collapses it afterward stays collapsed.
    _study_area_opened: bool = False

    def set_language(self, lang: str | list[str]):
        raw = lang[0] if isinstance(lang, (list, tuple)) and lang else lang
        if raw in st.SUPPORTED_LANGUAGES:
            self.language = raw

    def adopt_lang_param(self):
        """Honour ``?lang=`` on page load.

        The Canada page is a separate state root, so the language cannot be
        read across from it — the link between the two carries it in the URL and
        this is the receiving end. Absent or unrecognised, the page keeps its own
        default (Portuguese here, English there).
        """
        requested = (self.router.page.params or {}).get("lang")
        if requested in st.SUPPORTED_LANGUAGES:
            self.language = requested

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open

    def toggle_legend(self):
        self.legend_open = not self.legend_open

    def adopt_viewport(self, narrow: bool):
        """Collapse the on-map legend on a phone, once per session.

        The default genuinely differs by screen size — on desktop the legend
        is a small box in a large corner, on a phone the same box covers a
        third of the only map there is, over exactly the pixels it describes
        — and a Reflex state default is one Python value that knows nothing
        about the client. Radix's `display` breakpoints cannot express it
        either: this is one boolean feeding `rx.cond`, not two variants to
        show and hide. So the viewport is asked once, from the browser, via
        `rx.call_script(..., callback=...)` — see
        `components/map_legend.py::map_legend`.

        Only ever collapses, so it can never fight a user who opened the
        legend themselves.
        """
        if self._viewport_adopted:
            return
        self._viewport_adopted = True
        if narrow:
            self.legend_open = False

    def set_como_usar_open(self, value: bool):
        self.como_usar_open = value

    def set_como_citar_open(self, value: bool):
        self.como_citar_open = value

    def set_ai_disclaimer_open(self, value: bool):
        self.ai_disclaimer_open = value

    def set_open_groups(self, value: str | list[str]):
        """The accordion's own `on_value_change` — every manual open/close
        of any group passes back through here as the whole new array
        (`type="multiple"`), same as any other controlled Radix component.
        Typed ``str | list[str]`` because Reflex's accordion event spec is
        shared with `type="single"`, which reports a bare string; this
        accordion is always `type="multiple"`, so `value` is a list in
        practice, but the signature has to accept both to pass Reflex's own
        event-handler type check."""
        self.open_groups = [value] if isinstance(value, str) else value

    def _open_study_area(self) -> None:
        """Expand the "Área de estudo" group the first time an analysis area
        is set — a first-time user has no reason to know controls like
        `buffer_preview_toggle_label` are buried inside a closed accordion
        group until something puts it in front of them. Called from every
        path that establishes a first subject (state/_point.py::
        set_study_point covers a plain click and a conglomerado click, which
        reuses it; state/_geometry.py::_apply_geometry covers a drawn/pasted/
        uploaded region) rather than threaded through each one's own return
        value, so a new entry point gets this for free by calling either.
        """
        if self._study_area_opened:
            return
        self._study_area_opened = True
        if "study_area" not in self.open_groups:
            self.open_groups = [*self.open_groups, "study_area"]

    @rx.var
    def tr(self) -> dict[str, str]:
        return get_translations(self.language)

    @rx.var
    def canada_href(self) -> str:
        """Link across to the Canada page, carrying the current language.

        The two pages have separate state roots, so the language cannot simply
        be read across — it travels in the URL. Without this, a user reading
        this page in English would land on ``/canada`` in whatever that page's
        default happens to be.
        """
        return f"/canada?lang={self.language}"
