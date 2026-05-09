from pydantic import BaseModel, ConfigDict, field_validator


class FetchCompetitorsRequest(BaseModel):
    asin: str
    domain: str
    geo: str

    @field_validator("asin")
    @classmethod
    def normalise_asin(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("domain", "geo")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class CompetitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asin: str
    title: str | None = None
    url: str | None = None
    brand: str | None = None
    price: float | None = None
    currency: str | None = None
    rating: float | None = None
    images: list = []
    amazon_domain: str | None = None


class CompetitorsResponse(BaseModel):
    competitors: list[CompetitorOut]
