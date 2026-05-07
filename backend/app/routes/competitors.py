from fastapi import APIRouter, Query

from ..schemas.competitors import FetchCompetitorsRequest
from ..services.competitors import fetch_competitors, get_competitors

router = APIRouter()


@router.get("")
def get_competitors_endpoint(parent_asin: str = Query(...)):
    competitors = get_competitors(parent_asin)
    return {"competitors": competitors}


@router.post("/fetch")
def fetch_competitors_endpoint(request: FetchCompetitorsRequest):
    competitors = fetch_competitors(request.asin, request.domain, request.geo)
    return {"competitors": competitors}
