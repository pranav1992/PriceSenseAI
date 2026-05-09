from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..repositories.product import ProductRepository
from ..schemas.products import ScrapeProductRequest, ScrapeProductResponse
from ..services.products import scrape_product

router = APIRouter()


def get_product_repo(db: Session = Depends(get_db)) -> ProductRepository:
    return ProductRepository(db)


@router.post("/scrape", response_model=ScrapeProductResponse)
def scrape_product_endpoint(
    request: ScrapeProductRequest,
    repo: ProductRepository = Depends(get_product_repo),
):
    product = scrape_product(request.asin, request.geo_location, request.domain, repo)
    return {"product": product}
