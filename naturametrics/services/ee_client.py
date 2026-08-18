"""Earth Engine initialisation and authentication.

Ported from Yvynation's ``utils/ee_service.py``, which already handles every
credential source we need, in the right priority order. Kept as a straight port
rather than a rewrite: it is load-bearing and it works.

Three sources, tried in order:

1. **Environment-variable service account** — ``EE_PRIVATE_KEY`` +
   ``EE_SERVICE_ACCOUNT_EMAIL``. This is the Cloud Run path (decision D10), and
   it is the one that must be exercised before the first deploy: Cloud Run has
   no ADC file, so if this path is broken the deployed app has no Earth Engine
   at all.
2. **Application Default Credentials** — the local development path.
3. **Service-account JSON file** — ``EE_SERVICE_ACCOUNT_JSON``.

``GCP_PROJECT_ID`` must be set; Earth Engine has required a project since the
high-volume endpoint migration. It defaults to ``ee-leandromet``, which is where
the Partner tier grant lives (decision D5) — a different project silently drops
to contributor limits.
"""

from __future__ import annotations

import logging
import os
import threading

import ee
from google.oauth2 import service_account

from ..config.settings import GCP_PROJECT_ID

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
]

_initialized = False
_init_lock = threading.Lock()


def _init_from_env_service_account(project_id: str) -> bool:
    private_key = os.environ.get("EE_PRIVATE_KEY")
    email = os.environ.get("EE_SERVICE_ACCOUNT_EMAIL")
    if not (private_key and email):
        return False
    try:
        # Secret Manager and shell env round-trips often turn real newlines into
        # the two characters \n; PEM parsing fails cryptically if they are left.
        private_key = private_key.replace("\\n", "\n")
        credentials = service_account.Credentials.from_service_account_info(
            {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": os.environ.get("EE_PRIVATE_KEY_ID", ""),
                "private_key": private_key,
                "client_email": email,
                "client_id": os.environ.get("EE_CLIENT_ID", ""),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            },
            scopes=_SCOPES,
        )
        ee.Initialize(credentials, project=project_id)
        logger.info("Earth Engine initialised with env-var service account (%s)", email)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("EE env-var service account failed: %s", exc)
        return False


def _init_from_adc(project_id: str) -> bool:
    try:
        ee.Initialize(project=project_id)
        logger.info("Earth Engine initialised with Application Default Credentials")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("EE ADC initialisation failed: %s", exc)
        return False


def _init_from_json_file(project_id: str) -> bool:
    path = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    if not (path and os.path.exists(path)):
        return False
    try:
        credentials = service_account.Credentials.from_service_account_file(
            path, scopes=_SCOPES
        )
        ee.Initialize(credentials, project=project_id)
        logger.info("Earth Engine initialised with service-account file %s", path)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("EE service-account file failed: %s", exc)
        return False


def initialize_earth_engine(project_id: str | None = None) -> bool:
    """Initialise Earth Engine once, trying each credential source in turn.

    Idempotent and thread-safe: the fan-out design calls this from many threads,
    and a double ``ee.Initialize`` is wasteful at best.

    Raises:
        RuntimeError: if no credential source works. Failing loudly here is
            deliberate — an app that starts without Earth Engine has nothing to
            show, and a late failure is far harder to diagnose.
    """
    global _initialized
    if _initialized:
        return True

    with _init_lock:
        if _initialized:
            return True

        project = project_id or GCP_PROJECT_ID
        for attempt in (
            _init_from_env_service_account,
            _init_from_adc,
            _init_from_json_file,
        ):
            if attempt(project):
                _initialized = True
                _post_init()
                return True

        raise RuntimeError(
            "Could not initialise Earth Engine. Set EE_PRIVATE_KEY + "
            "EE_SERVICE_ACCOUNT_EMAIL (Cloud Run), or authenticate locally with "
            "`earthengine authenticate`, or point EE_SERVICE_ACCOUNT_JSON at a key "
            f"file. Project: {project}"
        )


def _post_init() -> None:
    """Work that can only happen after ``ee.Initialize``."""
    from .ee_concurrency import tune_ee_connection_pool

    tune_ee_connection_pool()


def is_initialized() -> bool:
    return _initialized


def get_ee():
    """Return the ``ee`` module, initialising on first use."""
    if not _initialized:
        initialize_earth_engine()
    return ee
