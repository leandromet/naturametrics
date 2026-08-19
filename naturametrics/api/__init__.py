"""Backend HTTP routes.

Reflex talks to the browser over a WebSocket, and that is the right channel for
everything the app normally exchanges — events and small state deltas. It is the
wrong channel for a half-megabyte of geometry: a state var is re-serialised into
the session, held in server memory for as long as the session lives, and
re-sent on every reload, none of which a static, identical-for-everyone
FeatureCollection needs.

So the biome polygons are served as an ordinary HTTP GET the browser can cache.
"""

from __future__ import annotations

import gzip
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..services import biomes

logger = logging.getLogger(__name__)

#: The asset is static, so the browser may hold it for a day.
_CACHE_CONTROL = "public, max-age=86400"


async def biomes_geojson(request: Request) -> Response:
    """The simplified IBGE biome polygons, pre-gzipped.

    ``Content-Encoding: gzip`` is set by hand rather than relying on compression
    middleware: the payload is compressed once, when it is built, and cached that
    way, so re-compressing it per request would be pure waste.

    The first call after a cold start builds it from Earth Engine (~5 s), then
    every later call is a memoised 1 ms. It is triggered by the user switching
    the layer on, and the control shows a spinner meanwhile.
    """
    try:
        payload = await _run_blocking(biomes.geojson_gzipped)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Biome GeoJSON could not be produced")
        return JSONResponse(
            {"error": "biomas indisponíveis", "detail": str(exc)}, status_code=503
        )

    headers = {"Cache-Control": _CACHE_CONTROL}
    # Every browser accepts gzip, but a client that says it does not gets the
    # plain bytes rather than an encoding it never asked for — announcing
    # Content-Encoding regardless would hand curl or a script an unreadable body.
    if "gzip" in request.headers.get("accept-encoding", ""):
        headers["Content-Encoding"] = "gzip"
    else:
        payload = await _run_blocking(lambda: gzip.decompress(payload))

    headers["Content-Length"] = str(len(payload))
    return Response(content=payload, media_type="application/geo+json",
                    headers=headers)


async def _run_blocking(fn):
    """Earth Engine and the disk cache are both blocking; the event loop is not."""
    import asyncio

    return await asyncio.get_running_loop().run_in_executor(None, fn)


def register(app) -> None:
    """Attach the routes to the Reflex app's Starlette instance."""
    api = getattr(app, "_api", None)
    if api is None:
        logger.warning("Reflex app exposes no Starlette instance — routes skipped")
        return
    api.add_route(biomes.GEOJSON_PATH, biomes_geojson, methods=["GET"])
    logger.info("Registered backend route %s", biomes.GEOJSON_PATH)
