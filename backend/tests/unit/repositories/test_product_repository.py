import pytest

from backend.app.models.product import Product
from backend.app.repositories.product import ProductRepository

pytestmark = pytest.mark.unit

_FULL_DATA = {
    "asin": "B07FZ8S74R",
    "title": "Test Product",
    "url": "https://amazon.com/dp/B07FZ8S74R",
    "brand": "TestBrand",
    "price": 29.99,
    "currency": "USD",
    "stock": "In Stock",
    "rating": 4.5,
    "images": ["https://img1.jpg"],
    "categories": ["Electronics"],
    "category_path": [{"name": "Electronics", "id": "1"}],
    "buybox": [{"seller": "Amazon"}],
    "product_overview": [{"label": "Color", "value": "Black"}],
    "amazon_domain": "amazon.com",
    "geo_location": "90210",
}


@pytest.fixture
def repo(db_session):
    return ProductRepository(db_session)


class TestGet:
    def test_returns_none_when_product_does_not_exist(self, repo):
        assert repo.get("NONEXISTENT") is None

    def test_returns_product_after_upsert(self, repo):
        repo.upsert(_FULL_DATA)
        product = repo.get("B07FZ8S74R")
        assert product is not None
        assert product.asin == "B07FZ8S74R"


class TestUpsert:
    def test_creates_new_product(self, repo, db_session):
        repo.upsert(_FULL_DATA)
        product = db_session.get(Product, "B07FZ8S74R")
        assert product is not None
        assert product.title == "Test Product"
        assert product.price == 29.99
        assert product.currency == "USD"
        assert product.stock == "In Stock"
        assert product.rating == 4.5
        assert product.brand == "TestBrand"
        assert product.images == ["https://img1.jpg"]
        assert product.amazon_domain == "amazon.com"
        assert product.geo_location == "90210"

    def test_updates_existing_product(self, repo, db_session):
        repo.upsert(_FULL_DATA)
        repo.upsert({**_FULL_DATA, "title": "Updated Title", "price": 19.99})
        product = db_session.get(Product, "B07FZ8S74R")
        assert product.title == "Updated Title"
        assert product.price == 19.99

    def test_does_not_create_duplicate_on_repeated_calls(self, repo, db_session):
        repo.upsert(_FULL_DATA)
        repo.upsert(_FULL_DATA)
        count = db_session.query(Product).filter(Product.asin == "B07FZ8S74R").count()
        assert count == 1

    def test_skips_when_data_has_no_asin(self, repo, db_session):
        repo.upsert({"title": "No ASIN product"})
        assert db_session.query(Product).count() == 0

    def test_stores_empty_lists_for_json_fields(self, repo, db_session):
        data = {**_FULL_DATA, "images": [], "categories": [], "category_path": []}
        repo.upsert(data)
        product = db_session.get(Product, "B07FZ8S74R")
        assert product.images == []
        assert product.categories == []


class TestAddAndDelete:
    def test_add_persists_product(self, repo, db_session):
        product = Product(asin="B00TEST001", title="Added directly")
        repo.add(product)
        repo.commit()
        fetched = db_session.get(Product, "B00TEST001")
        assert fetched is not None
        assert fetched.title == "Added directly"

    def test_delete_removes_product(self, repo, db_session):
        product = Product(asin="B00TEST002", title="To delete")
        repo.add(product)
        repo.commit()
        repo.delete(product)
        repo.commit()
        assert db_session.get(Product, "B00TEST002") is None

    def test_flush_makes_changes_visible_within_session(self, repo, db_session):
        product = Product(asin="B00TEST003", title="Flushed")
        repo.add(product)
        repo.flush()
        fetched = db_session.get(Product, "B00TEST003")
        assert fetched is not None
