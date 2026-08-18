"""Reflex configuration.

Ports avoid every other project on this machine (Yvynation 3000/8000; terra_web
3000/3003/3004/3005) — see doc/08-dev-environment.md §5.

Cloud Run (decision D10) injects ``PORT``; the backend must bind a *different*
port or the two fight for the same socket.
"""

import os

import reflex as rx

config = rx.Config(
    app_name="naturametrics",
    app_module_import="naturametrics.naturametrics",
    db_url=os.environ.get("REFLEX_DB_URL", "sqlite:///reflex.db"),
    log_level=os.environ.get("REFLEX_LOG_LEVEL", "info"),
    frontend_port=int(os.environ.get("PORT", 3010)),
    backend_port=int(os.environ.get("BACKEND_PORT", 8011)),
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
