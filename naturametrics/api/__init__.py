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
from ..services import auto_infracao, biomes, embargos, gbif, ifn

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


async def embargos_geojson(request: Request) -> Response:
    """IBAMA embargo polygons inside a viewport, proxied live per pan.

    Unlike ``ifn_points_geojson``, the backing call does real network I/O
    against a third party and can genuinely throw — ``embargos.polygons_in_bbox``
    already catches everything internally and returns an empty FeatureCollection
    on failure, but this try/except is the belt-and-suspenders match for
    ``biomes_geojson``'s pattern in case something upstream of that (e.g. the
    executor itself) misbehaves.
    """
    west = _float_param(request, "west")
    south = _float_param(request, "south")
    east = _float_param(request, "east")
    north = _float_param(request, "north")
    if None in (west, south, east, north):
        west, south, east, north = -180.0, -90.0, 180.0, 90.0

    try:
        payload = await _run_blocking(
            lambda: embargos.polygons_in_bbox(west, south, east, north)
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("IBAMA embargos GeoJSON could not be produced")
        return JSONResponse(
            {"error": "embargos indisponíveis", "detail": str(exc)}, status_code=503
        )

    # Live, per-viewport content — never cached by the browser, same reasoning
    # as ifn_points_geojson.
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


async def auto_infracao_geojson(request: Request) -> Response:
    """IBAMA infraction-notice points inside a viewport, proxied live per pan.

    Same shape as embargos_geojson — see that docstring for why the
    try/except is here even though auto_infracao.points_in_bbox already
    catches everything internally.
    """
    west = _float_param(request, "west")
    south = _float_param(request, "south")
    east = _float_param(request, "east")
    north = _float_param(request, "north")
    if None in (west, south, east, north):
        west, south, east, north = -180.0, -90.0, 180.0, 90.0

    try:
        payload = await _run_blocking(
            lambda: auto_infracao.points_in_bbox(west, south, east, north)
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("IBAMA auto de infração GeoJSON could not be produced")
        return JSONResponse(
            {"error": "autos de infração indisponíveis", "detail": str(exc)},
            status_code=503,
        )

    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


async def gbif_geojson(request: Request) -> Response:
    """GBIF occurrences inside a viewport, filtered by the accordion.

    The one route here that carries more than a bounding box: the whole taxon /
    basis-of-record / year / UF filter set rides in the query string and is
    forwarded upstream, because at this layer's zoom a viewport can hold tens of
    thousands of records and only 300 come back. Filtering client-side would be
    filtering an arbitrary 300, not the data.

    ``gbif.filters_from_query`` validates every parameter rather than trusting
    it — this is a public route whose values end up in a third-party query
    string, and a bad integer has to degrade to "no filter" rather than to a
    500 on every map pan.
    """
    west = _float_param(request, "west")
    south = _float_param(request, "south")
    east = _float_param(request, "east")
    north = _float_param(request, "north")
    if None in (west, south, east, north):
        west, south, east, north = -180.0, -90.0, 180.0, 90.0

    filters = gbif.filters_from_query(request.query_params)
    try:
        payload = await _run_blocking(
            lambda: gbif.points_in_bbox(west, south, east, north, filters)
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GBIF GeoJSON could not be produced")
        return JSONResponse(
            {"error": "ocorrências GBIF indisponíveis", "detail": str(exc)},
            status_code=503,
        )

    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


def register(app) -> None:
    """Attach the routes to the Reflex app's Starlette instance."""
    api = getattr(app, "_api", None)
    if api is None:
        logger.warning("Reflex app exposes no Starlette instance — routes skipped")
        return
    api.add_route(biomes.GEOJSON_PATH, biomes_geojson, methods=["GET"])
    api.add_route(ifn.GEOJSON_PATH, ifn_points_geojson, methods=["GET"])
    api.add_route(embargos.GEOJSON_PATH, embargos_geojson, methods=["GET"])
    api.add_route(auto_infracao.GEOJSON_PATH, auto_infracao_geojson, methods=["GET"])
    api.add_route(gbif.GEOJSON_PATH, gbif_geojson, methods=["GET"])
    logger.info("Registered backend routes %s, %s, %s, %s, %s",
                biomes.GEOJSON_PATH, ifn.GEOJSON_PATH, embargos.GEOJSON_PATH,
                auto_infracao.GEOJSON_PATH, gbif.GEOJSON_PATH)
