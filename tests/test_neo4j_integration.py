"""
tests/test_neo4j_integration.py
───────────────────────────────
Phase 4 test suite:
  1. Unit tests (Credential-Free):
     - Parameter validation & clamping.
     - Offline graceful degradation when Neo4j is disconnected.
     - Batch ingestion preparation logic (restaurants, users, reviews).
     - Dry-run simulation tests.
  2. Integration tests (Conditional):
     - Live queries against Neo4j Aura when connected.
     - Automatically skipped if NEO4J_URI or credentials are unavailable.
     - Strictly non-destructive.
"""

import pytest
from unittest.mock import patch, MagicMock

from database.neo4j_queries import (
    get_restaurants_by_category,
    get_similar_restaurants,
    get_common_reviewers,
    get_collaborative_recommendations,
    get_restaurant_graph_summary,
    get_graph_metrics,
)
from database.neo4j_connection import check_neo4j_connection
from data_pipeline.import_neo4j import (
    import_restaurants_batch,
    import_users_batch,
    import_reviews_batch,
)


class TestNeo4jQueryUnitValidation:
    """Unit tests for query parameter validation without requiring Neo4j."""

    def test_invalid_category_returns_empty(self):
        assert get_restaurants_by_category("") == []
        assert get_restaurants_by_category(None) == []

    def test_invalid_similar_restaurants_returns_empty(self):
        assert get_similar_restaurants("") == []
        assert get_similar_restaurants(None) == []

    def test_common_reviewers_validation(self):
        assert get_common_reviewers("", "b2") == []
        assert get_common_reviewers("b1", "") == []
        assert get_common_reviewers(None, "b2") == []
        # Same restaurant compared with itself should return empty
        assert get_common_reviewers("same_id", "same_id") == []

    def test_invalid_collaborative_recommendations_returns_empty(self):
        assert get_collaborative_recommendations("") == []
        assert get_collaborative_recommendations(None) == []

    def test_invalid_graph_summary_returns_none(self):
        assert get_restaurant_graph_summary("") is None
        assert get_restaurant_graph_summary(None) is None


class TestNeo4jOfflineDegradation:
    """Test safe handling when Neo4j is offline or disconnected."""

    @patch("database.neo4j_queries.run_query", return_value=[])
    def test_offline_queries_return_empty(self, mock_run):
        assert get_restaurants_by_category("Pizza") == []
        assert get_similar_restaurants("b1") == []
        assert get_common_reviewers("b1", "b2") == []
        assert get_collaborative_recommendations("b1") == []
        assert get_restaurant_graph_summary("b1") is None

    @patch("database.neo4j_queries.run_query", return_value=[])
    def test_offline_graph_metrics_returns_zeroes(self, mock_run):
        metrics = get_graph_metrics()
        assert metrics["restaurant_count"] == 0
        assert metrics["user_count"] == 0
        assert metrics["reviewed_count"] == 0


class TestNeo4jBatchImporterUnit:
    """Unit tests for batch preparation logic and dry-run execution."""

    def test_import_restaurants_batch_dry_run(self):
        batch = [
            {
                "business_id": "b1",
                "name": "Luigi Pizza",
                "categories": ["Restaurants", "Italian", "Pizza"],
                "stars": 4.5,
                "city": "Tampa",
                "state": "FL",
                "is_synthetic": True,
            },
            {
                "business_id": "b2",
                "name": "Burger Bar",
                "categories": "Food, Burgers",  # String categories
                "stars": 4.0,
                "city": "Tampa",
                "is_synthetic": True,
            },
            {
                "missing_business_id": "bad",
                "name": "Invalid Rest",
            },
        ]
        proc, fail = import_restaurants_batch(batch, dry_run=True)
        assert proc == 2
        assert fail == 0

    def test_import_users_batch_dry_run(self):
        batch = [
            {"user_id": "u1", "name": "Alice M.", "average_stars": 4.2},
            {"user_id": "u2", "name": "Bob K.", "average_stars": 3.8},
            {"missing_id": "bad"},
        ]
        proc, fail = import_users_batch(batch, dry_run=True)
        assert proc == 2
        assert fail == 0

    def test_import_reviews_batch_dry_run(self):
        batch = [
            {"review_id": "r1", "user_id": "u1", "business_id": "b1", "stars": 5.0},
            {"review_id": "r2", "user_id": "u2", "business_id": "b1", "stars": 4.0},
            {"missing_review_id": "r3", "user_id": "u1", "business_id": "b1"},
            {"review_id": "r4", "missing_user": "u1", "business_id": "b1"},
        ]
        proc, fail = import_reviews_batch(batch, dry_run=True)
        assert proc == 2
        assert fail == 0


# ── Live Integration Tests (Conditional) ───────────────────────────────────────

neo4j_alive, _ = check_neo4j_connection()


@pytest.mark.skipif(not neo4j_alive, reason="Neo4j Aura cluster is not configured or unreachable")
class TestLiveNeo4jIntegration:
    """Live tests executed against active Neo4j Aura cluster."""

    def test_live_graph_metrics(self):
        metrics = get_graph_metrics()
        assert isinstance(metrics, dict)
        assert "restaurant_count" in metrics
        assert "reviewed_count" in metrics

    def test_live_category_query(self):
        results = get_restaurants_by_category("Restaurants", limit=5)
        assert isinstance(results, list)

    def test_live_similar_restaurants(self):
        # Run query with dummy id; should return empty list without error
        results = get_similar_restaurants("non_existent_id", limit=5)
        assert isinstance(results, list)
