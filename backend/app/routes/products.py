from fastapi import APIRouter

from ..schemas.products import ScrapeProductRequest
from ..services.products import scrape_product

router = APIRouter()


@router.post("/scrape")
def scrape_product_endpoint(request: ScrapeProductRequest):
    product = scrape_product(request.asin, request.geo_location)
    return {"product": product}
