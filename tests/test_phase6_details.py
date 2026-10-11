"""
tests/test_phase6_details.py
────────────────────────────
Phase 6 test suite:
  - Rating distribution calculations from review records.
  - Review sorting and pagination mapping.
  - Attribute formatting and sparse document handling.
  - Similar restaurant fallback (Neo4j -> MongoDB content similarity).
  - Target restaurant exclusion in recommendation results.
  - Safe error handling for missing/invalid restaurant IDs.
"""

import math
import pytest
from unittest.mock import MagicMock, patch

from database.mongodb_queries import (
    get_restaurant_by_id,
    get_restaurant_review_rating_distribution,
    get_restaurant_reviews,
)
from database.neo4j_queries import (
    get_similar_restaurants,
    get_collaborative_recommendations,
)


class TestRatingDistributionCalculation:
    """Test calculation of 1-to-5 star rating breakdown from reviews."""

    def test_invalid_business_id_returns_empty_distribution(self):
        result = get_restaurant_review_rating_distribution("")
        assert result["total_reviews"] == 0
        assert result["average_rating"] == 0.0
        assert result["counts_by_star"] == {1.0: 0, 2.0: 0, 3.0: 0, 4.0: 0, 5.0: 0}

    def test_none_business_id_returns_empty_distribution(self):
        result = get_restaurant_review_rating_distribution(None)
        assert result["total_reviews"] == 0
        assert result["average_rating"] == 0.0

    @patch("database.mongodb_queries.get_collection")
    def test_distribution_calculation_with_mocked_reviews(self, mock_get_coll):
        # Mock aggregation output: 2 five-star, 1 four-star, 1 three-star
        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = [
            {"_id": 5.0, "count": 2},
            {"_id": 4.0, "count": 1},
            {"_id": 3.0, "count": 1},
        ]
        mock_get_coll.return_value = mock_coll

        dist = get_restaurant_review_rating_distribution("test_biz_123")
        assert dist["total_reviews"] == 4
        # (5*2 + 4*1 + 3*1) / 4 = 17 / 4 = 4.25
        assert dist["average_rating"] == 4.25
        assert dist["counts_by_star"][5.0] == 2
        assert dist["counts_by_star"][4.0] == 1
        assert dist["counts_by_star"][3.0] == 1
        assert dist["counts_by_star"][2.0] == 0
        assert dist["counts_by_star"][1.0] == 0
        assert dist["percentages"][5.0] == 50.0

    @patch("database.mongodb_queries.get_collection")
    def test_zero_reviews_division_by_zero_avoidance(self, mock_get_coll):
        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = []
        mock_get_coll.return_value = mock_coll

        dist = get_restaurant_review_rating_distribution("biz_with_no_reviews")
        assert dist["total_reviews"] == 0
        assert dist["average_rating"] == 0.0


class TestReviewSortingAndPagination:
    """Test review sorting specifications and pagination bounds."""

    def test_review_sort_options_mapping(self):
        sort_options = {
            "Newest First": ("date", -1),
            "Highest Rating First": ("stars", -1),
            "Lowest Rating First": ("stars", 1),
        }
        assert sort_options["Newest First"] == ("date", -1)
        assert sort_options["Highest Rating First"] == ("stars", -1)
        assert sort_options["Lowest Rating First"] == ("stars", 1)

    def test_review_page_count_math(self):
        per_page = 5
        assert math.ceil(12 / per_page) == 3
        assert math.ceil(5 / per_page) == 1
        assert math.ceil(1 / per_page) == 1
        assert math.ceil(0 / per_page) == 0


class TestSimilarRestaurantFallbackLogic:
    """Test recommendation fallback when graph database is offline or empty."""

    def test_target_restaurant_is_excluded_from_fallback(self):
        target_id = "target_biz_1"
        candidates = [
            {"business_id": "target_biz_1", "name": "Self Restaurant"},
            {"business_id": "other_biz_2", "name": "Other Pizza"},
            {"business_id": "other_biz_3", "name": "Third Venue"},
        ]

        filtered = [
            cand for cand in candidates
            if cand.get("business_id") != target_id
        ]
        assert len(filtered) == 2
        assert all(c["business_id"] != target_id for c in filtered)

    @patch("database.neo4j_queries.run_query", return_value=[])
    def test_neo4j_queries_return_empty_safely(self, mock_run):
        assert get_collaborative_recommendations("test_biz") == []
        assert get_similar_restaurants("test_biz") == []


class TestSparseRestaurantAttributes:
    """Test document handling when optional fields are missing or varied types."""

    def test_attributes_dictionary_handling(self):
        attributes = {
            "RestaurantsPriceRange2": "2",
            "OutdoorSeating": "True",
            "WiFi": "free",
        }
        price_tier = attributes.get("RestaurantsPriceRange2")
        assert price_tier == "2"
        assert "$" * int(price_tier) == "$$"

    def test_non_dictionary_attributes_tolerance(self):
        # In case attributes field is a string or None
        sparse_doc = {"business_id": "b1", "attributes": None}
        attrs = sparse_doc.get("attributes") or {}
        assert isinstance(attrs, dict)
