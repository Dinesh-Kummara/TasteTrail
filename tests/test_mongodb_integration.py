"""
tests/test_mongodb_integration.py
──────────────────────────────────
Phase 3 test suite:
  1. Unit tests:
     - Filter builder logic (regex, text search, city, category, rating).
     - Sorting criteria mapping.
     - Input validation and empty/invalid ID handling.
     - Graceful degradation when MongoDB is unreachable.
  2. Integration tests:
     - Live queries against MongoDB Atlas when connected.
     - Automatically skipped when MONGODB_URI is absent or unreachable.
     - Non-destructive: never drops collections or deletes existing records.
"""

import pytest
from unittest.mock import MagicMock, patch

from database.mongodb_queries import (
    build_restaurant_filter,
    build_sort_criteria,
    search_restaurants,
    get_restaurant_by_id,
    get_restaurant_reviews,
    get_top_rated_restaurants,
    get_most_reviewed_restaurants,
    get_distinct_cities,
    get_distinct_categories,
    get_dashboard_metrics,
)
from database.mongodb_connection import check_mongodb_connection
from data_pipeline.import_mongodb import bulk_upsert_collection


class TestQueryBuilderUnit:
    """Unit tests for MongoDB query construction without database connection."""

    def test_build_empty_filter(self):
        query = build_restaurant_filter()
        assert query == {}

    def test_build_name_filter_regex(self):
        query = build_restaurant_filter(name="Pizza Place")
        assert "name" in query
        assert query["name"]["$regex"] == "Pizza\\ Place"
        assert query["name"]["$options"] == "i"

    def test_build_name_filter_text_search(self):
        query = build_restaurant_filter(name="Pasta", use_regex_for_name=False)
        assert "$text" in query
        assert query["$text"] == {"$search": "Pasta"}

    def test_build_city_filter(self):
        query = build_restaurant_filter(city="Tampa")
        assert "city" in query
        assert query["city"]["$regex"] == "^Tampa$"
        assert query["city"]["$options"] == "i"

    def test_build_category_filter(self):
        query = build_restaurant_filter(category="Italian")
        assert "categories" in query
        assert query["categories"]["$regex"] == "^Italian$"
        assert query["categories"]["$options"] == "i"

    def test_build_min_stars_filter(self):
        query = build_restaurant_filter(min_stars=3.5)
        assert "stars" in query
        assert query["stars"] == {"$gte": 3.5}

    def test_build_is_open_filter(self):
        query = build_restaurant_filter(is_open_only=True)
        assert query.get("is_open") == 1

    def test_build_combined_filter(self):
        query = build_restaurant_filter(
            name="Luigi",
            category="Pizza",
            city="Philadelphia",
            min_stars=4.0,
            is_open_only=True,
        )
        assert "name" in query
        assert "categories" in query
        assert "city" in query
        assert query["stars"] == {"$gte": 4.0}
        assert query["is_open"] == 1

    def test_sort_criteria_mapping(self):
        # Default rating descending
        assert build_sort_criteria("rating", -1) == [("stars", -1), ("review_count", -1)]
        # Rating ascending
        assert build_sort_criteria("rating", 1) == [("stars", 1), ("review_count", -1)]
        # Reviews descending
        assert build_sort_criteria("reviews", -1) == [("review_count", -1), ("stars", -1)]
        # Name ascending
        assert build_sort_criteria("name", 1) == [("name", 1)]
        # Name descending
        assert build_sort_criteria("name", -1) == [("name", -1)]


class TestQueryGracefulDegradation:
    """Test safe handling when MongoDB is disconnected or returns empty results."""

    def test_invalid_business_id_returns_none(self):
        assert get_restaurant_by_id("") is None
        assert get_restaurant_by_id(None) is None

    def test_invalid_business_id_reviews_returns_empty(self):
        assert get_restaurant_reviews("") == ([], 0)
        assert get_restaurant_reviews(None) == ([], 0)

    @patch("database.mongodb_queries.get_collection", return_value=None)
    def test_offline_search_returns_empty_tuple(self, mock_get_coll):
        results, count = search_restaurants(name="Any")
        assert results == []
        assert count == 0

    @patch("database.mongodb_queries.get_collection", return_value=None)
    def test_offline_top_rated_returns_empty_list(self, mock_get_coll):
        results = get_top_rated_restaurants()
        assert results == []

    @patch("database.mongodb_queries.get_collection", return_value=None)
    def test_offline_most_reviewed_returns_empty_list(self, mock_get_coll):
        results = get_most_reviewed_restaurants()
        assert results == []

    @patch("database.mongodb_queries.get_collection", return_value=None)
    def test_offline_distinct_cities_returns_empty_list(self, mock_get_coll):
        cities = get_distinct_cities()
        assert cities == []

    @patch("database.mongodb_queries.get_collection", return_value=None)
    def test_offline_distinct_categories_returns_empty_list(self, mock_get_coll):
        cats = get_distinct_categories()
        assert cats == []

    @patch("database.mongodb_queries.get_database", return_value=None)
    def test_offline_dashboard_metrics_returns_defaults(self, mock_get_db):
        metrics = get_dashboard_metrics()
        assert metrics["total_restaurants"] == 0
        assert metrics["total_reviews"] == 0
        assert metrics["average_rating"] == 0.0


class TestBulkUpsertLogic:
    """Unit tests for bulk upsert operations with mocks."""

    def test_bulk_upsert_dry_run(self, tmp_path):
        test_file = tmp_path / "test.jsonl"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('{"business_id": "b1", "name": "Test Rest"}\n')
            f.write('{"business_id": "b2", "name": "Second Rest"}\n')
            f.write('{"missing_id": "none", "name": "Bad Rec"}\n')

        metrics = bulk_upsert_collection(
            collection=None,
            file_path=test_file,
            id_field="business_id",
            batch_size=10,
            dry_run=True,
        )

        assert metrics["total_read"] == 3
        assert metrics["upserted"] == 2
        assert metrics["skipped_missing_id"] == 1


# ── Live Integration Tests (Conditional) ───────────────────────────────────────

mongo_alive, _ = check_mongodb_connection()


@pytest.mark.skipif(not mongo_alive, reason="MongoDB Atlas is not configured or offline")
class TestLiveMongoDBIntegration:
    """Live integration tests running against active MongoDB Atlas cluster."""

    def test_live_search_runs_without_error(self):
        results, count = search_restaurants(page=1, page_size=5)
        assert isinstance(results, list)
        assert isinstance(count, int)
        assert count >= len(results)

    def test_live_distinct_facets(self):
        cities = get_distinct_cities()
        assert isinstance(cities, list)

        categories = get_distinct_categories(limit=10)
        assert isinstance(categories, list)

    def test_live_dashboard_metrics(self):
        metrics = get_dashboard_metrics()
        assert "total_restaurants" in metrics
        assert "average_rating" in metrics
        assert isinstance(metrics["average_rating"], float)
