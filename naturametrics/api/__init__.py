"""Backend HTTP routes.

Reflex talks to the browser over a WebSocket, and that is the right channel for
everything the app normally exchanges — events and small state deltas. It is the
wrong channel for a half-megabyte of geometry: a state var is re-serialised into
the session, held in server memory for as long as the session lives, and
re-sent on every reload, none of which a static, identical-for-everyone
FeatureCollection needs.

So the biome polygons are served as an ordinary HTTP GET the browser can cache,
and so are the conglomerados currently in view — which additionally change on
every pan, and would otherwise mean a state round trip per map movement.
"""

from __future__ import annotations

import gzip
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config.settings import IFN_VIEWPORT_LIMIT
from ..services import biomes, ifn

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


def _float_param(request: Request, name: str) -> float | None:
    raw = request.query_params.get(name)
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


async def ifn_points_geojson(request: Request) -> Response:
    """The conglomerados inside a bounding box, matching the current filters.

    Served over HTTP rather than pushed through state because it is re-asked on
    every pan and zoom. Answered from the in-memory point table — a linear scan
    of 17 479 rows, measured at 9 ms — so no Earth Engine and no database is in
    this path, and the layer keeps up with a dragged map.

    ``bbox`` is ``west,south,east,north`` in degrees. Without it the whole
    country is returned, subject to ``limit``.
    """
    west = _float_param(request, "west")
    south = _float_param(request, "south")
    east = _float_param(request, "east")
    north = _float_param(request, "north")
    if None in (west, south, east, north):
        west, south, east, north = -180.0, -90.0, 180.0, 90.0

    try:
        limit = int(request.query_params.get("limit", IFN_VIEWPORT_LIMIT))
    except ValueError:
        limit = IFN_VIEWPORT_LIMIT
    limit = max(1, min(limit, IFN_VIEWPORT_LIMIT))

    payload = await _run_blocking(lambda: ifn.points_in_bbox(
        west, south, east, north,
        region=request.query_params.get("region", ""),
        uf=request.query_params.get("uf", ""),
        municipality=request.query_params.get("municipality", ""),
        biome=request.query_params.get("biome", ""),
        limit=limit,
    ))
    # Deliberately not cached by the browser: the filters are in the query
    # string, but a stale viewport response is worse than a 9 ms recompute.
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


def register(app) -> None:
    """Attach the routes to the Reflex app's Starlette instance."""
    api = getattr(app, "_api", None)
    if api is None:
        logger.warning("Reflex app exposes no Starlette instance — routes skipped")
        return
    api.add_route(biomes.GEOJSON_PATH, biomes_geojson, methods=["GET"])
    api.add_route(ifn.GEOJSON_PATH, ifn_points_geojson, methods=["GET"])
    logger.info("Registered backend routes %s, %s",
                biomes.GEOJSON_PATH, ifn.GEOJSON_PATH)
