import pytest
from pydantic import ValidationError

from backend.app.schemas.products import ProductOut, ScrapeProductRequest, ScrapeProductResponse

pytestmark = pytest.mark.unit


class TestScrapeProductRequest:
    def test_asin_is_uppercased(self):
        req = ScrapeProductRequest(asin="b07fz8s74r", geo_location="90210")
        assert req.asin == "B07FZ8S74R"

    def test_asin_is_stripped(self):
        req = ScrapeProductRequest(asin="  B07FZ8S74R  ", geo_location="90210")
        assert req.asin == "B07FZ8S74R"

    def test_geo_location_is_stripped(self):
        req = ScrapeProductRequest(asin="B07FZ8S74R", geo_location="  90210  ")
        assert req.geo_location == "90210"

    def test_domain_defaults_to_com(self):
        req = ScrapeProductRequest(asin="B07FZ8S74R", geo_location="90210")
        assert req.domain == "com"

    def test_domain_is_stripped(self):
        req = ScrapeProductRequest(asin="B07FZ8S74R", geo_location="90210", domain="  co.uk  ")
        assert req.domain == "co.uk"

    def test_missing_asin_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeProductRequest(geo_location="90210")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("asin",) for e in errors)

    def test_missing_geo_location_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeProductRequest(asin="B07FZ8S74R")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("geo_location",) for e in errors)


class TestProductOut:
    def test_accepts_full_data(self):
        data = {
            "asin": "B07FZ8S74R",
            "title": "Test Product",
            "url": "https://amazon.com/dp/B07FZ8S74R",
            "brand": "TestBrand",
            "price": 29.99,
            "currency": "USD",
            "stock": "In Stock",
            "rating": 4.5,
            "images": ["https://img.jpg"],
            "categories": ["Electronics"],
            "category_path": [{"name": "Electronics"}],
            "buybox": [{"seller": "Amazon"}],
            "product_overview": [{"label": "Color", "value": "Black"}],
            "amazon_domain": "amazon.com",
            "geo_location": "90210",
        }
        out = ProductOut.model_validate(data)
        assert out.asin == "B07FZ8S74R"
        assert out.title == "Test Product"
        assert out.price == 29.99
        assert out.images == ["https://img.jpg"]

    def test_optional_fields_default_to_none(self):
        out = ProductOut.model_validate({"asin": "B07FZ8S74R"})
        assert out.title is None
        assert out.url is None
        assert out.brand is None
        assert out.price is None
        assert out.currency is None
        assert out.stock is None
        assert out.rating is None
        assert out.amazon_domain is None
        assert out.geo_location is None

    def test_list_fields_default_to_empty_list(self):
        out = ProductOut.model_validate({"asin": "B07FZ8S74R"})
        assert out.images == []
        assert out.categories == []
        assert out.category_path == []
        assert out.buybox == []
        assert out.product_overview == []

    def test_missing_asin_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ProductOut.model_validate({"title": "No ASIN"})

    def test_extra_fields_in_source_dict_are_ignored(self):
        out = ProductOut.model_validate({"asin": "B07FZ8S74R", "unknown_field": "ignored"})
        assert out.asin == "B07FZ8S74R"
        assert not hasattr(out, "unknown_field")


class TestScrapeProductResponse:
    def test_wraps_product_out(self):
        resp = ScrapeProductResponse(product=ProductOut(asin="B07FZ8S74R"))
        assert resp.product.asin == "B07FZ8S74R"

    def test_serializes_to_dict_with_product_key(self):
        resp = ScrapeProductResponse(product=ProductOut(asin="B07FZ8S74R"))
        data = resp.model_dump()
        assert "product" in data
        assert data["product"]["asin"] == "B07FZ8S74R"
