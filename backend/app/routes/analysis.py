from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..repositories.competitor import CompetitorRepository
from ..repositories.product import ProductRepository
from ..schemas.analysis import AnalysisResponse, InsightsResponse
from ..services.analysis import compute_price_stats, compute_price_suggestion, compute_stock_signal
from ..services.insights import get_ai_insights

router = APIRouter()


def _build_analysis(asin: str, db: Session) -> tuple[AnalysisResponse, str | None, float | None]:
    product_repo = ProductRepository(db)
    competitor_repo = CompetitorRepository(db)

    product = product_repo.get(asin)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {asin} not found. Scrape it first.")

    competitors = competitor_repo.get_by_parent_asin(asin)
    price_stats = compute_price_stats(competitors)

    suggestion = None
    if price_stats and product.price is not None:
        competitor_ratings = [c.rating for c in competitors if c.rating is not None]
        suggestion = compute_price_suggestion(
            product.price, price_stats, product.rating, competitor_ratings
        )

    stock_signal = compute_stock_signal(product.stock)

    analysis = AnalysisResponse(
        asin=asin,
        current_price=product.price,
        price_stats=price_stats,
        suggestion=suggestion,
        stock_signal=stock_signal,
    )
    return analysis, product.title, product.currency or "USD"


@router.get("/{asin}", response_model=AnalysisResponse)
def get_analysis(asin: str, db: Session = Depends(get_db)):
    asin = asin.strip().upper()
    analysis, _, _ = _build_analysis(asin, db)
    return analysis


@router.post("/{asin}/insights", response_model=InsightsResponse)
def get_insights(asin: str, db: Session = Depends(get_db)):
    asin = asin.strip().upper()
    analysis, title, currency = _build_analysis(asin, db)
    return get_ai_insights(asin, title, analysis.current_price, analysis, currency)
