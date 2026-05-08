from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_asin: Mapped[str] = mapped_column(String(20), index=True)
    asin: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(10))
    rating: Mapped[float | None] = mapped_column(Float)
    images: Mapped[list | None] = mapped_column(JSON)
    amazon_domain: Mapped[str | None] = mapped_column(String(50))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "asin": self.asin,
            "title": self.title,
            "url": self.url,
            "brand": self.brand,
            "price": self.price,
            "currency": self.currency,
            "rating": self.rating,
            "images": self.images or [],
            "amazon_domain": self.amazon_domain,
        }
