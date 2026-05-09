import pytest
from pydantic import ValidationError

from backend.app.schemas.competitors import (
    CompetitorOut,
    CompetitorsResponse,
    FetchCompetitorsRequest,
)

pytestmark = pytest.mark.unit


class TestFetchCompetitorsRequest:
    def test_asin_is_uppercased(self):
        req = FetchCompetitorsRequest(asin="b07fz8s74r", domain="com", geo="90210")
        assert req.asin == "B07FZ8S74R"

    def test_asin_is_stripped(self):
        req = FetchCompetitorsRequest(asin="  B07FZ8S74R  ", domain="com", geo="90210")
        assert req.asin == "B07FZ8S74R"

    def test_domain_is_stripped(self):
        req = FetchCompetitorsRequest(asin="B07FZ8S74R", domain="  com  ", geo="90210")
        assert req.domain == "com"

    def test_geo_is_stripped(self):
        req = FetchCompetitorsRequest(asin="B07FZ8S74R", domain="com", geo="  90210  ")
        assert req.geo == "90210"

    def test_missing_asin_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            FetchCompetitorsRequest(domain="com", geo="90210")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("asin",) for e in errors)

    def test_missing_domain_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            FetchCompetitorsRequest(asin="B07FZ8S74R", geo="90210")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("domain",) for e in errors)

    def test_missing_geo_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            FetchCompetitorsRequest(asin="B07FZ8S74R", domain="com")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("geo",) for e in errors)


class TestCompetitorOut:
    def test_accepts_full_data(self):
        data = {
            "asin": "B00COMP0001",
            "title": "Competitor A",
            "url": "https://amazon.com/dp/B00COMP0001",
            "brand": "BrandA",
            "price": 24.99,
            "currency": "USD",
            "rating": 4.2,
            "images": ["https://img-a.jpg"],
            "amazon_domain": "amazon.com",
        }
        out = CompetitorOut.model_validate(data)
        assert out.asin == "B00COMP0001"
        assert out.title == "Competitor A"
        assert out.price == 24.99
        assert out.images == ["https://img-a.jpg"]

    def test_optional_fields_default_to_none(self):
        out = CompetitorOut.model_validate({"asin": "B00COMP0001"})
        assert out.title is None
        assert out.url is None
        assert out.brand is None
        assert out.price is None
        assert out.currency is None
        assert out.rating is None
        assert out.amazon_domain is None

    def test_images_defaults_to_empty_list(self):
        out = CompetitorOut.model_validate({"asin": "B00COMP0001"})
        assert out.images == []

    def test_missing_asin_raises_validation_error(self):
        with pytest.raises(ValidationError):
            CompetitorOut.model_validate({"title": "No ASIN"})


class TestCompetitorsResponse:
    def test_wraps_list_under_competitors_key(self):
        competitors = [CompetitorOut(asin="B00COMP0001"), CompetitorOut(asin="B00COMP0002")]
        resp = CompetitorsResponse(competitors=competitors)
        assert len(resp.competitors) == 2

    def test_accepts_empty_list(self):
        resp = CompetitorsResponse(competitors=[])
        assert resp.competitors == []

    def test_serializes_to_dict_with_competitors_key(self):
        resp = CompetitorsResponse(competitors=[CompetitorOut(asin="B00COMP0001")])
        data = resp.model_dump()
        assert "competitors" in data
        assert data["competitors"][0]["asin"] == "B00COMP0001"
