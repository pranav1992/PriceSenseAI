from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Product(Base):
    __tablename__ = "products"

    asin: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(10))
    stock: Mapped[str | None] = mapped_column(String(50))
    rating: Mapped[float | None] = mapped_column(Float)
    images: Mapped[list | None] = mapped_column(JSON)
    categories: Mapped[list | None] = mapped_column(JSON)
    category_path: Mapped[list | None] = mapped_column(JSON)
    buybox: Mapped[list | None] = mapped_column(JSON)
    product_overview: Mapped[list | None] = mapped_column(JSON)
    amazon_domain: Mapped[str | None] = mapped_column(String(50))
    geo_location: Mapped[str | None] = mapped_column(String(100))
    scraped_at: Mapped[datetime] = mapped_column(
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
            "stock": self.stock,
            "rating": self.rating,
            "images": self.images or [],
            "categories": self.categories or [],
            "category_path": self.category_path or [],
            "buybox": self.buybox or [],
            "product_overview": self.product_overview or [],
            "amazon_domain": self.amazon_domain,
            "geo_location": self.geo_location,
        }
