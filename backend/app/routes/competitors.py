from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..repositories.competitor import CompetitorRepository
from ..schemas.competitors import CompetitorsResponse, FetchCompetitorsRequest
from ..services.competitors import fetch_competitors, get_competitors

router = APIRouter()


def get_competitor_repo(db: Session = Depends(get_db)) -> CompetitorRepository:
    return CompetitorRepository(db)


@router.get("", response_model=CompetitorsResponse)
def get_competitors_endpoint(
    parent_asin: str = Query(...),
    repo: CompetitorRepository = Depends(get_competitor_repo),
):
    competitors = get_competitors(parent_asin, repo)
    return {"competitors": competitors}


@router.post("/fetch", response_model=CompetitorsResponse)
def fetch_competitors_endpoint(
    request: FetchCompetitorsRequest,
    repo: CompetitorRepository = Depends(get_competitor_repo),
):
    competitors = fetch_competitors(request.asin, request.domain, request.geo, repo)
    return {"competitors": competitors}
