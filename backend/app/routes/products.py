from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..schemas.products import ScrapeProductRequest
from ..services.products import scrape_product

router = APIRouter()


@router.post("/scrape")
def scrape_product_endpoint(request: ScrapeProductRequest, db: Session = Depends(get_db)):
    product = scrape_product(request.asin, request.geo_location, request.domain, db)
    return {"product": product}
