from sqlalchemy.orm import Session

from ..models.competitor import Competitor
from .base import BaseRepository


class CompetitorRepository(BaseRepository[Competitor]):
    def __init__(self, db: Session) -> None:
        super().__init__(Competitor, db)

    def get_by_parent_asin(self, parent_asin: str) -> list[Competitor]:
        return self.db.query(Competitor).filter(Competitor.parent_asin == parent_asin).all()

    def replace_for_parent(self, parent_asin: str, items: list[dict]) -> None:
        self.db.query(Competitor).filter(Competitor.parent_asin == parent_asin).delete()
        for item in items:
            if not item.get("asin"):
                continue
            self.db.add(Competitor(
                parent_asin=parent_asin,
                asin=item["asin"],
                title=item.get("title"),
                url=item.get("url"),
                brand=item.get("brand"),
                price=item.get("price"),
                currency=item.get("currency"),
                rating=item.get("rating"),
                images=item.get("images", []),
                amazon_domain=item.get("amazon_domain"),
            ))
        self.commit()
