from sqlalchemy.orm import Session

from ..models.product import Product
from .base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: Session) -> None:
        super().__init__(Product, db)

    def upsert(self, data: dict) -> None:
        asin = data.get("asin")
        if not asin:
            return

        product = self.get(asin)
        if product is None:
            product = Product(asin=asin)
            self.add(product)

        product.title = data.get("title")
        product.url = data.get("url")
        product.brand = data.get("brand")
        product.price = data.get("price")
        product.currency = data.get("currency")
        product.stock = data.get("stock")
        product.rating = data.get("rating")
        product.images = data.get("images", [])
        product.categories = data.get("categories", [])
        product.category_path = data.get("category_path", [])
        product.buybox = data.get("buybox", [])
        product.product_overview = data.get("product_overview", [])
        product.amazon_domain = data.get("amazon_domain")
        product.geo_location = data.get("geo_location")

        self.commit()
