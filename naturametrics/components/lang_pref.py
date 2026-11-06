"""Which language a UmaTerra page opens in: the same order for every platform.

This is the portal's rule (its root page does it before the first paint), applied
in each app:

1. ``?lang=`` in the address: a link from another platform or the portal carries
   the reader's language, and a language the app speaks wins;
2. the language the reader chose here before, remembered in this site's
   ``localStorage`` under ``umaterra-lang`` (a switcher change stores it);
3. the browser's preferred languages (``navigator.languages``), the first one
   the app speaks;
4. the app's own default.

Reflex apps read this on load with ``rx.call_script`` and a callback (see
``detect_language`` and ``apply_detected_language`` in each state); the switcher
stores its choice with ``store_script``. Shared by Naturametrics, Camposcope and
Yvynation, checked by hash: edit the canonical copy in Naturametrics, then run
``python scripts/sync_shared_files.py`` there.
"""

from __future__ import annotations

import json

import reflex as rx

#: The key the portal uses too, so one choice is remembered across the suite on
#: one origin (each subdomain keeps its own storage).
STORAGE_KEY = "umaterra-lang"


def detect_script(supported: tuple[str, ...]) -> str:
    """JavaScript expression that evaluates to the language to open in, or ``""``."""
    return f"""(function () {{
  var supported = {json.dumps(list(supported))};
  var q = new URLSearchParams(location.search).get('lang');
  if (supported.indexOf(q) >= 0) return q;
  var stored = null;
  try {{ stored = localStorage.getItem('{STORAGE_KEY}'); }} catch (e) {{}}
  if (supported.indexOf(stored) >= 0) return stored;
  var prefs = (navigator.languages && navigator.languages.length)
    ? navigator.languages : [navigator.language || ''];
  for (var i = 0; i < prefs.length; i++) {{
    var code = String(prefs[i] || '').slice(0, 2).toLowerCase();
    if (supported.indexOf(code) >= 0) return code;
  }}
  return '';
}})()"""


def store_script(lang: str) -> str:
    """JavaScript that remembers the reader's choice for the next visit."""
    return (f"try {{ localStorage.setItem('{STORAGE_KEY}', {json.dumps(lang)}); }} "
            "catch (e) {}")


def detect_language_event(state_cls, supported: tuple[str, ...]):
    """The on-load event: run ``detect_script`` in the browser and hand the answer to
    ``apply_detected_language`` of the same state."""
    return rx.call_script(detect_script(supported), callback=state_cls.apply_detected_language)
