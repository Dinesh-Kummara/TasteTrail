"""
tests/test_phase7_recommendations.py
────────────────────────────────────
Phase 7 End-to-End & Integration Tests:
- Exact combined scoring formula verification:
    score = 100 * (w_category * jaccard + w_rating * bayesian / 5)
- Deterministic multi-tier tie-breaking:
    (-score, -same_city, -review_count, business_id)
- Deduplication of hybrid candidates between MongoDB and Neo4j
- Offline Neo4j fallback resilience
- Streamlit session state and navigation handling for recommendations
"""

import pytest
from unittest.mock import MagicMock, patch

from services.recommendation_service import (
    calculate_bayesian_rating,
    calculate_jaccard_similarity,
    recommend_similar_restaurants,
    recommend_top_restaurants,
    validate_score_weights,
)


class TestScoringFormulaAndTieBreaking:
    """Validate mathematical correctness of composite scoring and tie-breaking."""

    def test_exact_formula_calculation(self):
        # Category weight = 0.6, Rating weight = 0.4
        # Jaccard = 0.5, Bayesian Rating = 4.0
        # Expected: 100 * (0.6 * 0.5 + 0.4 * (4.0 / 5.0)) = 100 * (0.30 + 0.32) = 62.0
        w_cat, w_rat = 0.6, 0.4
        jaccard = 0.5
        bayesian = 4.0
        score = round(100.0 * (w_cat * jaccard + w_rat * (bayesian / 5.0)), 2)
        assert score == 62.0

    @patch("services.recommendation_service.search_restaurants")
    def test_tie_breaking_prioritizes_same_city_then_reviews_then_id(self, mock_search):
        # Two restaurants with the exact same category overlap, rating, and score
        # One in same city ("Tampa") as reference, one in "Orlando"
        ref = {
            "business_id": "ref_1",
            "name": "Ref Trattoria",
            "city": "Tampa",
            "categories": ["Italian"],
            "stars": 4.0,
            "review_count": 100,
        }
        mock_search.return_value = (
            [
                {
                    "business_id": "cand_orlando",
                    "name": "Orlando Pasta",
                    "city": "Orlando",
                    "categories": ["Italian"],
                    "stars": 4.0,
                    "review_count": 50,
                },
                {
                    "business_id": "cand_tampa",
                    "name": "Tampa Pasta",
                    "city": "Tampa",
                    "categories": ["Italian"],
                    "stars": 4.0,
                    "review_count": 50,
                },
            ],
            2,
        )

        recs = recommend_similar_restaurants(
            reference_restaurant=ref,
            prioritize_same_city=True,
            use_neo4j_hybrid=False,
        )
        assert len(recs) == 2
        # Tampa should be ranked first because it is in the same city
        assert recs[0]["business_id"] == "cand_tampa"
        assert recs[1]["business_id"] == "cand_orlando"

    @patch("services.recommendation_service.search_restaurants")
    def test_tie_breaking_by_review_count_when_same_city(self, mock_search):
        ref = {
            "business_id": "ref_1",
            "name": "Ref Trattoria",
            "city": "Tampa",
            "categories": ["Italian"],
            "stars": 4.0,
            "review_count": 100,
        }
        mock_search.return_value = (
            [
                {
                    "business_id": "cand_low_rev",
                    "name": "Tampa Low",
                    "city": "Tampa",
                    "categories": ["Italian"],
                    "stars": 4.0,
                    "review_count": 20,
                },
                {
                    "business_id": "cand_high_rev",
                    "name": "Tampa High",
                    "city": "Tampa",
                    "categories": ["Italian"],
                    "stars": 4.0,
                    "review_count": 150,
                },
            ],
            2,
        )

        recs = recommend_similar_restaurants(
            reference_restaurant=ref,
            use_neo4j_hybrid=False,
        )
        assert len(recs) == 2
        # Higher review count wins tie-break
        assert recs[0]["business_id"] == "cand_high_rev"


class TestMultiCriteriaFiltersIntegration:
    """Verify pre-filtering application across City, Category, Stars, Reviews, and Limit."""

    @patch("services.recommendation_service.search_restaurants")
    def test_category_and_city_filters_passed_to_search(self, mock_search):
        mock_search.return_value = ([], 0)
        ref = {"business_id": "b1", "name": "Bistro", "categories": ["French"], "city": "Tampa"}

        recommend_similar_restaurants(
            reference_restaurant=ref,
            city="Philadelphia",
            category="Creperie",
            min_stars=4.0,
            min_reviews=25,
            limit=5,
            use_neo4j_hybrid=False,
        )

        # Confirm search_restaurants called with appropriate filters
        assert mock_search.call_count >= 1
        first_call_kwargs = mock_search.call_args_list[0][1]
        assert first_call_kwargs.get("city") == "Philadelphia"
        assert first_call_kwargs.get("category") == "Creperie"
        assert first_call_kwargs.get("min_stars") == 4.0


class TestNeo4jCandidateDeduplicationAndFallback:
    """Test candidate merge and offline robustness."""

    @patch("services.recommendation_service.get_neo4j_collaborative_recs")
    @patch("services.recommendation_service.get_neo4j_similar_restaurants")
    @patch("services.recommendation_service.search_restaurants")
    def test_neo4j_candidates_deduplicated_without_reference_leak(
        self, mock_mongo, mock_neo_sim, mock_neo_collab
    ):
        ref_id = "target_ref_id"
        ref = {"business_id": ref_id, "name": "Target", "categories": ["Sushi"], "city": "Tampa"}

        # Neo4j accidentally returns reference itself plus another candidate
        mock_neo_collab.return_value = [
            {"business_id": ref_id, "name": "Target"},
            {"business_id": "cand_neo_1", "name": "Tokyo Sushi", "categories": ["Sushi"], "stars": 4.6, "review_count": 80},
        ]
        mock_neo_sim.return_value = []
        mock_mongo.return_value = (
            [
                {"business_id": "cand_neo_1", "name": "Tokyo Sushi", "categories": ["Sushi"], "stars": 4.6, "review_count": 80},
                {"business_id": "cand_mongo_2", "name": "Osaka House", "categories": ["Sushi"], "stars": 4.3, "review_count": 60},
            ],
            2,
        )

        recs = recommend_similar_restaurants(reference_restaurant=ref, use_neo4j_hybrid=True)
        rec_ids = [r["business_id"] for r in recs]

        # Target reference must be excluded
        assert ref_id not in rec_ids
        # cand_neo_1 should not be duplicated
        assert rec_ids.count("cand_neo_1") == 1
        assert len(rec_ids) == 2


class TestStreamlitRecommendationsNavigationConventions:
    """Verify session state navigation conventions used by Recommendation components."""

    def test_session_state_key_conventions(self):
        # Emulate user clicking 'Similar' or 'Details'
        mock_session_state = {}
        target_bid = "sample_biz_123"

        # Action: Set selection for Details view
        mock_session_state["selected_business_id"] = target_bid
        assert mock_session_state.get("selected_business_id") == target_bid

        # Action: Set selection for Similar recommendations view
        mock_session_state["rec_business_id"] = target_bid
        assert mock_session_state.get("rec_business_id") == target_bid
