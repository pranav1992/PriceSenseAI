import pytest

from backend.app.models.competitor import Competitor
from backend.app.repositories.competitor import CompetitorRepository

pytestmark = pytest.mark.unit

_PARENT_ASIN = "B07PARENT01"

_ITEMS = [
    {
        "asin": "B00COMP0001",
        "title": "Competitor A",
        "url": "https://amazon.com/dp/B00COMP0001",
        "brand": "BrandA",
        "price": 24.99,
        "currency": "USD",
        "rating": 4.2,
        "images": ["https://img-a.jpg"],
        "amazon_domain": "amazon.com",
    },
    {
        "asin": "B00COMP0002",
        "title": "Competitor B",
        "url": "https://amazon.com/dp/B00COMP0002",
        "brand": "BrandB",
        "price": 19.99,
        "currency": "USD",
        "rating": 3.8,
        "images": [],
        "amazon_domain": "amazon.com",
    },
]


@pytest.fixture
def repo(db_session):
    return CompetitorRepository(db_session)


class TestGetByParentAsin:
    def test_returns_empty_list_when_none_exist(self, repo):
        assert repo.get_by_parent_asin(_PARENT_ASIN) == []

    def test_returns_only_matching_competitors(self, repo, db_session):
        db_session.add(Competitor(parent_asin=_PARENT_ASIN, asin="B00COMP0001"))
        db_session.add(Competitor(parent_asin="B07OTHER001", asin="B00COMP0002"))
        db_session.commit()
        results = repo.get_by_parent_asin(_PARENT_ASIN)
        assert len(results) == 1
        assert results[0].asin == "B00COMP0001"

    def test_returns_all_matching_competitors(self, repo, db_session):
        for item in _ITEMS:
            db_session.add(Competitor(parent_asin=_PARENT_ASIN, asin=item["asin"]))
        db_session.commit()
        results = repo.get_by_parent_asin(_PARENT_ASIN)
        assert len(results) == 2


class TestReplaceForParent:
    def test_inserts_new_competitors(self, repo, db_session):
        repo.replace_for_parent(_PARENT_ASIN, _ITEMS)
        rows = db_session.query(Competitor).filter(
            Competitor.parent_asin == _PARENT_ASIN
        ).all()
        assert len(rows) == 2
        asins = {r.asin for r in rows}
        assert asins == {"B00COMP0001", "B00COMP0002"}

    def test_maps_all_fields(self, repo, db_session):
        repo.replace_for_parent(_PARENT_ASIN, [_ITEMS[0]])
        row = db_session.query(Competitor).filter(
            Competitor.parent_asin == _PARENT_ASIN
        ).one()
        assert row.title == "Competitor A"
        assert row.url == "https://amazon.com/dp/B00COMP0001"
        assert row.brand == "BrandA"
        assert row.price == 24.99
        assert row.currency == "USD"
        assert row.rating == 4.2
        assert row.images == ["https://img-a.jpg"]
        assert row.amazon_domain == "amazon.com"

    def test_deletes_existing_before_inserting(self, repo, db_session):
        repo.replace_for_parent(_PARENT_ASIN, _ITEMS)
        repo.replace_for_parent(_PARENT_ASIN, [_ITEMS[0]])
        rows = db_session.query(Competitor).filter(
            Competitor.parent_asin == _PARENT_ASIN
        ).all()
        assert len(rows) == 1
        assert rows[0].asin == "B00COMP0001"

    def test_does_not_delete_other_parents(self, repo, db_session):
        other_asin = "B07OTHER001"
        db_session.add(Competitor(parent_asin=other_asin, asin="B00OTHER001"))
        db_session.commit()
        repo.replace_for_parent(_PARENT_ASIN, _ITEMS)
        other_count = db_session.query(Competitor).filter(
            Competitor.parent_asin == other_asin
        ).count()
        assert other_count == 1

    def test_skips_items_without_asin(self, repo, db_session):
        items = [{"title": "No ASIN"}, _ITEMS[0]]
        repo.replace_for_parent(_PARENT_ASIN, items)
        count = db_session.query(Competitor).filter(
            Competitor.parent_asin == _PARENT_ASIN
        ).count()
        assert count == 1

    def test_empty_list_clears_all_competitors(self, repo, db_session):
        repo.replace_for_parent(_PARENT_ASIN, _ITEMS)
        repo.replace_for_parent(_PARENT_ASIN, [])
        count = db_session.query(Competitor).filter(
            Competitor.parent_asin == _PARENT_ASIN
        ).count()
        assert count == 0
