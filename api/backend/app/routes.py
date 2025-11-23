"""HTTP route registrations for the FastAPI presentation layer."""

import json
import os
import tempfile
from typing import List

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from application import service_facade
from domain.schemas import CityBase, GraphBase, RegionBase, RegionInfoBase


def build_router(logger) -> APIRouter:
    """Create an APIRouter wired up with the project endpoints."""
    router = APIRouter(prefix="/api")

    async def _load_graph_base(
        city_id: int,
        regions_ids: List[int],
        request: Request,
        use_cache: bool,
        request_label: str,
    ) -> tuple[GraphBase, str]:
        os.makedirs("./data/caches", exist_ok=True)

        regions_key = "_".join(map(str, sorted(regions_ids)))
        cache_response_file_path = f"./data/caches/{city_id}_{regions_key}.json"

        if use_cache and os.path.exists(cache_response_file_path):
            try:
                with open(
                    cache_response_file_path, "r", encoding="utf-8"
                ) as cached_file:
                    cached_data = json.load(cached_file)
                required_keys = {
                    "edges_csv",
                    "points_csv",
                    "ways_properties_csv",
                    "points_properties_csv",
                    "metrics_csv",
                    "access_nodes_csv",
                    "access_edges_csv",
                }
                if (
                    isinstance(cached_data, dict)
                    and required_keys.issubset(cached_data.keys())
                    and all(
                        isinstance(cached_data.get(key), str) for key in required_keys
                    )
                ):
                    try:
                        return GraphBase(**cached_data), regions_key
                    except Exception:
                        logger.warning(
                            "Cached graph payload failed validation, regenerating: {}",
                            cache_response_file_path,
                        )
                else:
                    logger.warning(
                        "Ignore invalid cache file: {}", cache_response_file_path
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to read cache {}: {}",
                    cache_response_file_path,
                    exc,
                )

        (
            points,
            edges,
            pprop,
            wprop,
            metrics,
            access_nodes,
            access_edges,
        ) = await service_facade.graph_from_ids(
            city_id=city_id,
            regions_ids=regions_ids,
            regions=request.app.state.regions_df,
        )

        if points is None:
            detail = f"Region not found or city {city_id} not downloaded. Requested regions: {regions_ids}"
            logger.error(f"{request_label} 404 {detail}")
            raise HTTPException(status_code=404, detail=detail)

        if len(points) == 0 or len(edges) == 0:
            detail = (
                f"No road network data found for region(s) {regions_ids} in city {city_id}. "
                "The data for this region has not been downloaded from OSM yet. Please ensure the region data is downloaded before requesting the graph."
            )
            logger.error(f"{request_label} 422 {detail}")
            raise HTTPException(status_code=422, detail=detail)

        graph_base = service_facade.graph_to_scheme(
            points,
            edges,
            pprop,
            wprop,
            metrics,
            access_nodes,
            access_edges,
        )
        data = (
            graph_base.model_dump()
            if hasattr(graph_base, "model_dump")
            else graph_base.dict()
        )

        try:
            dirpath = os.path.dirname(cache_response_file_path)
            with tempfile.NamedTemporaryFile(
                "w", dir=dirpath, delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(data, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_name = tmp.name
            os.replace(tmp_name, cache_response_file_path)
        except Exception as exc:
            logger.warning(
                "Failed to write cache {}: {}", cache_response_file_path, exc
            )

        return graph_base, regions_key

    @router.get("/city/", response_model=CityBase)
    @logger.catch(exclude=HTTPException)
    async def get_city(city_id: int):
        request_label = f"GET /api/city?city_id={city_id}"
        status_code = 200
        detail = "OK"

        city = await service_facade.get_city(city_id=city_id)
        if city is None:
            status_code = 404
            detail = "NOT FOUND"
            logger.error(f"{request_label} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail)

        logger.info(f"{request_label} {status_code} {detail}")
        return city

    @router.get("/cities/", response_model=List[CityBase])
    @logger.catch(exclude=HTTPException)
    async def get_cities(page: int = Query(ge=0), per_page: int = Query(gt=0)):
        request_label = f"GET /api/cities?page={page}&per_page={per_page}/"
        status_code = 200
        detail = "OK"

        cities = await service_facade.get_cities(page=page, per_page=per_page)
        if cities is None:
            cities = []

        logger.info(f"{request_label} {status_code} {detail}")
        return cities

    @router.get("/regions/city/", response_model=List[RegionBase])
    @logger.catch(exclude=HTTPException)
    async def city_regions(request: Request, city_id: int):
        request_label = f"GET /api/regions/city?city_id={city_id}/"
        status_code = 200
        detail = "OK"

        regions = await service_facade.get_regions(
            city_id=city_id,
            regions=request.app.state.regions_df,
            cities=request.app.state.cities_info,
        )
        if regions is None:
            status_code = 404
            detail = "NOT FOUND"
            logger.error(f"{request_label} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail)

        logger.info(f"{request_label} {status_code} {detail}")
        return regions

    @router.get("/regions/info/", response_model=List[RegionInfoBase])
    @logger.catch(exclude=HTTPException)
    async def city_regions_info(request: Request, city_id: int):
        request_label = f"GET /api/regions/info?city_id={city_id}/"
        status_code = 200
        detail = "OK"

        regions = await service_facade.get_regions_info(
            city_id=city_id,
            regions=request.app.state.regions_df,
            cities=request.app.state.cities_info,
        )
        if regions is None:
            status_code = 404
            detail = "NOT FOUND"
            logger.error(f"{request_label} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail)

        logger.info(f"{request_label} {status_code} {detail}")
        return regions

    @router.post("/city/graph/region/", response_model=GraphBase)
    @logger.catch(exclude=HTTPException)
    async def city_graph(
        request: Request,
        city_id: int,
        regions_ids: List[int] = Body(...),
        use_cache: bool = True,
    ):
        request_label = f"POST /api/city/graph/region/?city_id={city_id} regions_ids={regions_ids} (body)"
        status_code = 200
        detail = "OK"

        try:
            graph_base, _ = await _load_graph_base(
                city_id=city_id,
                regions_ids=regions_ids,
                request=request,
                use_cache=use_cache,
                request_label=request_label,
            )

            logger.info(f"{request_label} {status_code} {detail}")
            return graph_base
        except HTTPException:
            raise
        except Exception as exc:
            status_code = 500
            error_type = type(exc).__name__
            error_msg = str(exc)
            detail = (
                f"Internal server error processing graph for city {city_id}, regions {regions_ids}. "
                f"Error: {error_type}: {error_msg}"
            )
            logger.exception(f"{request_label} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail) from exc

    @router.post("/city/graph/region/export/")
    @logger.catch(exclude=HTTPException)
    async def city_graph_export(
        request: Request,
        city_id: int,
        regions_ids: List[int] = Body(...),
        use_cache: bool = True,
    ):
        request_label = f"POST /api/city/graph/region/export/?city_id={city_id} regions_ids={regions_ids} (body)"
        status_code = 200
        detail = "OK"

        try:
            graph_base, regions_key = await _load_graph_base(
                city_id=city_id,
                regions_ids=regions_ids,
                request=request,
                use_cache=use_cache,
                request_label=request_label,
            )
            archive_buffer = service_facade.graph_to_zip(graph_base)
            archive_bytes = archive_buffer.getvalue()
            filename_suffix = regions_key or "all"
            headers = {
                "Content-Disposition": f'attachment; filename="city_{city_id}_{filename_suffix}.zip"'
            }

            logger.info(f"{request_label} {status_code} {detail}")
            return StreamingResponse(
                iter([archive_bytes]),
                media_type="application/zip",
                headers=headers,
            )
        except HTTPException:
            raise
        except Exception as exc:
            status_code = 500
            error_type = type(exc).__name__
            error_msg = str(exc)
            detail = (
                f"Internal server error preparing export for city {city_id}, regions {regions_ids}. "
                f"Error: {error_type}: {error_msg}"
            )
            logger.exception(f"{request_label} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail) from exc

    @router.post("/city/graph/bbox/{city_id}/", response_model=GraphBase)
    @logger.catch(exclude=HTTPException)
    async def city_graph_poly(city_id: int, polygons_as_list: List[List[List[float]]]):
        request_label = f"POST /api/city/graph/bbox/{city_id}/"
        status_code = 200
        detail = "OK"

        polygon = service_facade.list_to_polygon(polygons=polygons_as_list)
        (
            points,
            edges,
            pprop,
            wprop,
            metrics,
            access_nodes,
            access_edges,
        ) = await service_facade.graph_from_poly(city_id=city_id, polygon=polygon)

        if points is None:
            status_code = 404
            detail = "NOT FOUND"
            logger.error(f"{request_label} {status_code} {detail}")
            raise HTTPException(status_code=status_code, detail=detail)

        logger.info(f"{request_label} {status_code} {detail}")
        return service_facade.graph_to_scheme(
            points,
            edges,
            pprop,
            wprop,
            metrics,
            access_nodes,
            access_edges,
        )

    return router
