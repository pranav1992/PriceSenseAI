import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]


def test_openapi_schema_exposes_product_scrape_endpoint(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    scrape_operation = schema["paths"]["/api/products/scrape"]["post"]

    assert scrape_operation["tags"] == ["products"]
    assert scrape_operation["summary"] == "Scrape Product Endpoint"
    assert (
        scrape_operation["requestBody"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == "#/components/schemas/ScrapeProductRequest"
    )


def test_openapi_schema_includes_scrape_request_contract(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    scrape_request = response.json()["components"]["schemas"]["ScrapeProductRequest"]

    assert scrape_request["type"] == "object"
    assert scrape_request["required"] == ["asin", "geo_location"]
    assert scrape_request["properties"]["asin"]["type"] == "string"
    assert scrape_request["properties"]["geo_location"]["type"] == "string"
