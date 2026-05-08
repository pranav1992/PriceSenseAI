from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..schemas.competitors import FetchCompetitorsRequest
from ..services.competitors import fetch_competitors, get_competitors

router = APIRouter()


@router.get("")
def get_competitors_endpoint(parent_asin: str = Query(...), db: Session = Depends(get_db)):
    competitors = get_competitors(parent_asin, db)
    return {"competitors": competitors}


@router.post("/fetch")
def fetch_competitors_endpoint(request: FetchCompetitorsRequest, db: Session = Depends(get_db)):
    competitors = fetch_competitors(request.asin, request.domain, request.geo, db)
    return {"competitors": competitors}
