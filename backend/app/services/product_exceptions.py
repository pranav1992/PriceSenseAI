from ..core.exceptions import AppException, ConfigurationError


class ProductServiceError(AppException):
    status_code = 500
    code = "PRODUCT_SERVICE_ERROR"
    default_message = "Product service failed."


class ProductScrapeConfigurationError(ConfigurationError):
    code = "PRODUCT_SCRAPE_CONFIGURATION_ERROR"
    default_message = "Product scraping provider is not configured correctly."


class ProductScrapeError(ProductServiceError):
    status_code = 502
    code = "PRODUCT_SCRAPE_FAILED"
    default_message = "Unable to scrape product details."


class ProductScrapeTimeoutError(ProductScrapeError):
    status_code = 504
    code = "PRODUCT_SCRAPE_TIMEOUT"
    default_message = "Product scraping provider timed out."


class ProductScrapeProviderError(ProductScrapeError):
    code = "PRODUCT_SCRAPE_PROVIDER_ERROR"
    default_message = "Product scraping provider returned an error."


class ProductScrapeUnavailableError(ProductScrapeError):
    code = "PRODUCT_SCRAPE_UNAVAILABLE"
    default_message = "Product scraping provider is unavailable."
