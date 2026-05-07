from pydantic import BaseModel


class FetchCompetitorsRequest(BaseModel):
    asin: str
    domain: str
    geo: str
