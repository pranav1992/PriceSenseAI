import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]


class TestProductsOpenAPI:
    def test_scrape_endpoint_is_registered(self, client):
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "/api/products/scrape" in schema["paths"]
        operation = schema["paths"]["/api/products/scrape"]["post"]
        assert operation["tags"] == ["products"]
        assert operation["summary"] == "Scrape Product Endpoint"

    def test_scrape_request_schema_requires_asin_and_geo_location(self, client):
        response = client.get("/openapi.json")
        schema = response.json()["components"]["schemas"]["ScrapeProductRequest"]

        assert schema["type"] == "object"
        assert "asin" in schema["required"]
        assert "geo_location" in schema["required"]
        assert schema["properties"]["asin"]["type"] == "string"
        assert schema["properties"]["geo_location"]["type"] == "string"

    def test_scrape_response_schema_is_registered(self, client):
        response = client.get("/openapi.json")
        schema = response.json()

        operation = schema["paths"]["/api/products/scrape"]["post"]
        response_ref = (
            operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        )
        assert "ScrapeProductResponse" in response_ref

    def test_product_out_schema_includes_all_fields(self, client):
        response = client.get("/openapi.json")
        schemas = response.json()["components"]["schemas"]

        assert "ProductOut" in schemas
        product_out = schemas["ProductOut"]
        expected_fields = {
            "asin", "title", "url", "brand", "price", "currency",
            "stock", "rating", "images", "categories", "category_path",
            "buybox", "product_overview", "amazon_domain", "geo_location",
        }
        assert expected_fields == set(product_out["properties"].keys())


class TestCompetitorsOpenAPI:
    def test_get_competitors_endpoint_is_registered(self, client):
        response = client.get("/openapi.json")
        schema = response.json()

        assert "/api/competitors" in schema["paths"]
        operation = schema["paths"]["/api/competitors"]["get"]
        assert operation["tags"] == ["competitors"]

    def test_fetch_competitors_endpoint_is_registered(self, client):
        response = client.get("/openapi.json")
        schema = response.json()

        assert "/api/competitors/fetch" in schema["paths"]
        operation = schema["paths"]["/api/competitors/fetch"]["post"]
        assert operation["tags"] == ["competitors"]

    def test_fetch_request_schema_requires_asin_domain_geo(self, client):
        response = client.get("/openapi.json")
        schema = response.json()["components"]["schemas"]["FetchCompetitorsRequest"]

        assert "asin" in schema["required"]
        assert "domain" in schema["required"]
        assert "geo" in schema["required"]

    def test_competitors_response_schema_is_registered(self, client):
        response = client.get("/openapi.json")
        schemas = response.json()["components"]["schemas"]

        assert "CompetitorsResponse" in schemas
        assert "CompetitorOut" in schemas

    def test_competitor_out_schema_includes_expected_fields(self, client):
        response = client.get("/openapi.json")
        competitor_out = response.json()["components"]["schemas"]["CompetitorOut"]

        expected_fields = {
            "asin", "title", "url", "brand", "price",
            "currency", "rating", "images", "amazon_domain",
        }
        assert expected_fields == set(competitor_out["properties"].keys())
