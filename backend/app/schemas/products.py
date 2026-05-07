from pydantic import BaseModel


class ScrapeProductRequest(BaseModel):
    asin: str
    geo_location: str
    domain: str = "com"
