import pytest

from backend.app.core.exceptions import AppException, ConfigurationError
from backend.app.services.product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)

pytestmark = pytest.mark.unit


def test_app_exception_uses_default_metadata():
    exc = AppException()

    assert exc.status_code == 500
    assert exc.code == "APPLICATION_ERROR"
    assert exc.message == "Application error."
    assert exc.details is None


def test_app_exception_allows_instance_overrides():
    exc = AppException(
        "Custom message.",
        code="CUSTOM_ERROR",
        status_code=418,
        details={"field": "value"},
    )

    assert exc.status_code == 418
    assert exc.code == "CUSTOM_ERROR"
    assert exc.message == "Custom message."
    assert exc.details == {"field": "value"}


@pytest.mark.parametrize(
    ("exception_type", "status_code", "code"),
    [
        (ConfigurationError, 500, "CONFIGURATION_ERROR"),
        (
            ProductScrapeConfigurationError,
            500,
            "PRODUCT_SCRAPE_CONFIGURATION_ERROR",
        ),
        (ProductScrapeError, 502, "PRODUCT_SCRAPE_FAILED"),
        (ProductScrapeProviderError, 502, "PRODUCT_SCRAPE_PROVIDER_ERROR"),
        (ProductScrapeUnavailableError, 502, "PRODUCT_SCRAPE_UNAVAILABLE"),
        (ProductScrapeTimeoutError, 504, "PRODUCT_SCRAPE_TIMEOUT"),
    ],
)
def test_exception_classes_expose_stable_error_contract(
    exception_type, status_code, code
):
    exc = exception_type()

    assert exc.status_code == status_code
    assert exc.code == code
    assert exc.message == exception_type.default_message
