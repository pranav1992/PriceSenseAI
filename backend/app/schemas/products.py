from pydantic import BaseModel, ConfigDict, field_validator


class ScrapeProductRequest(BaseModel):
    asin: str
    geo_location: str
    domain: str = "com"

    @field_validator("asin")
    @classmethod
    def normalise_asin(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("geo_location", "domain")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asin: str
    title: str | None = None
    url: str | None = None
    brand: str | None = None
    price: float | None = None
    currency: str | None = None
    stock: str | None = None
    rating: float | None = None
    images: list = []
    categories: list = []
    category_path: list = []
    buybox: list = []
    product_overview: list = []
    amazon_domain: str | None = None
    geo_location: str | None = None


class ScrapeProductResponse(BaseModel):
    product: ProductOut
