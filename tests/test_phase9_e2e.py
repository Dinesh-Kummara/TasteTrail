"""
tests/test_phase9_e2e.py
────────────────────────
Phase 9 End-to-End Integration & Deployment Readiness Test Suite:
1. End-to-end user journeys (Homepage -> Explore -> Details -> Recommendations -> Analytics).
2. Session state propagation & navigation stability.
3. Multi-database graceful degradation (MongoDB offline, Neo4j offline).
4. Empty dataset & zero-match search robustness across all components.
5. Deployment configuration verification (.streamlit/config.toml, .env.example, .gitignore).
"""

import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from config.settings import validate_config
from database.mongodb_queries import (
    build_restaurant_filter,
    build_sort_criteria,
    search_restaurants,
    get_restaurant_by_id,
    get_restaurant_review_rating_distribution,
    get_top_rated_restaurants,
)
from services.recommendation_service import (
    recommend_similar_restaurants,
    recommend_top_restaurants,
)
from services.analytics_service import (
    get_kpi_summary,
    prepare_rankings_export_df,
    prepare_category_export_df,
    prepare_city_export_df,
    create_rating_distribution_chart,
)


class TestEndToEndUserJourneys:
    """Verify state transitions and data flow across user journey milestones."""

    def test_journey_homepage_search_to_explore_filter(self):
        """Simulate user searching on Homepage and propagating to Explore page."""
        session_state = {}

        # 1. User enters search term on homepage
        user_query = "Pizza"
        user_city = "Tampa"

        # 2. Homepage sets exploration session state
        session_state["explore_name"] = user_query
        session_state["explore_city"] = user_city
        session_state["explore_cat"] = "All"
        session_state["explore_current_page"] = 1

        assert session_state["explore_name"] == "Pizza"
        assert session_state["explore_city"] == "Tampa"
        assert session_state["explore_current_page"] == 1

        # 3. Explore query builder receives propagated terms
        mongo_filter = build_restaurant_filter(
            name=session_state["explore_name"],
            city=session_state["explore_city"],
        )
        assert "$regex" in mongo_filter["name"]
        assert "$regex" in mongo_filter["city"]

    @patch("database.mongodb_queries.get_collection")
    def test_journey_explore_to_restaurant_details(self, mock_get_coll):
        """Simulate selecting restaurant card and viewing details."""
        mock_coll = MagicMock()
        mock_doc = {
            "business_id": "test_venue_99",
            "name": "Bistro Deluxe",
            "city": "Tampa",
            "stars": 4.5,
            "review_count": 150,
            "categories": ["French", "Bistros"],
        }
        mock_coll.find_one.return_value = mock_doc
        mock_get_coll.return_value = mock_coll

        session_state = {}
        # User clicks 'Details 📖' on card
        session_state["selected_business_id"] = "test_venue_99"

        # Details page retrieves venue by ID
        venue = get_restaurant_by_id(session_state["selected_business_id"])
        assert venue is not None
        assert venue["name"] == "Bistro Deluxe"
        assert venue["business_id"] == "test_venue_99"

    @patch("services.recommendation_service.search_restaurants")
    def test_journey_details_to_recommendations(self, mock_search):
        """Simulate user opening recommendations directly from a restaurant details page."""
        session_state = {}
        ref_venue = {
            "business_id": "ref_99",
            "name": "Bistro Deluxe",
            "city": "Tampa",
            "stars": 4.5,
            "review_count": 150,
            "categories": ["French", "Bistros"],
        }
        session_state["rec_business_id"] = ref_venue["business_id"]

        mock_search.return_value = (
            [
                {
                    "business_id": "cand_1",
                    "name": "French Brasserie",
                    "city": "Tampa",
                    "categories": ["French"],
                    "stars": 4.4,
                    "review_count": 80,
                }
            ],
            1,
        )

        recs = recommend_similar_restaurants(
            reference_restaurant=ref_venue,
            city="Tampa",
            use_neo4j_hybrid=False,
        )
        assert len(recs) == 1
        assert recs[0]["business_id"] == "cand_1"
        assert recs[0]["recommendation_score"] > 0
        assert "French" in recs[0]["explanation"]

    def test_journey_analytics_export_flow(self):
        """Simulate generating and exporting tabular summaries from the analytics page."""
        sample_venues = [
            {"business_id": "v1", "name": "Pasta Place", "city": "Tampa", "stars": 4.8, "review_count": 210, "categories": ["Italian"]}
        ]
        sample_cats = [{"category": "Italian", "count": 25, "avg_rating": 4.3}]
        sample_cities = [{"city": "Tampa", "count": 50, "avg_rating": 4.15}]

        # Prepare export DataFrames
        df_venues = prepare_rankings_export_df(sample_venues)
        df_cats = prepare_category_export_df(sample_cats)
        df_cities = prepare_city_export_df(sample_cities)

        # Confirm non-empty exports with expected schema
        assert not df_venues.empty
        assert "Rank" in df_venues.columns
        assert not df_cats.empty
        assert "Restaurant Count" in df_cats.columns
        assert not df_cities.empty
        assert "Average Rating" in df_cities.columns

        # Verify UTF-8 CSV serialization for Streamlit download button
        csv_bytes = df_venues.to_csv(index=False).encode("utf-8")
        assert len(csv_bytes) > 0


class TestErrorAndOfflineResilience:
    """Ensure graceful degradation when databases are offline or return empty data."""

    def test_mongodb_offline_queries_do_not_crash(self):
        with patch("database.mongodb_queries.get_collection", return_value=None):
            rests, count = search_restaurants()
            assert rests == []
            assert count == 0

            top = get_top_rated_restaurants()
            assert top == []

            doc = get_restaurant_by_id("nonexistent")
            assert doc is None

            dist = get_restaurant_review_rating_distribution("nonexistent")
            assert dist["total_reviews"] == 0

    def test_neo4j_offline_recommendations_fallback_cleanly(self):
        ref = {"business_id": "ref_1", "name": "Diner", "categories": ["American"], "city": "Tampa"}
        with patch("services.recommendation_service.get_neo4j_collaborative_recs", side_effect=Exception("Neo4j Offline")):
            with patch("services.recommendation_service.search_restaurants") as mock_search:
                mock_search.return_value = (
                    [{"business_id": "c1", "name": "Grill", "categories": ["American"], "stars": 4.0, "review_count": 20}],
                    1,
                )
                recs = recommend_similar_restaurants(reference_restaurant=ref, use_neo4j_hybrid=True)
                assert len(recs) == 1
                assert recs[0]["business_id"] == "c1"

    def test_analytics_charts_with_empty_data_render_gracefully(self):
        fig = create_rating_distribution_chart([])
        assert fig is not None
        assert "No rating data" in fig.layout.annotations[0].text


class TestDeploymentReadinessAndConfiguration:
    """Validate project structure, deployment settings, and security hygiene."""

    def test_streamlit_config_toml_exists_and_configured(self):
        base_dir = Path(__file__).resolve().parent.parent
        config_path = base_dir / ".streamlit" / "config.toml"
        assert config_path.exists(), ".streamlit/config.toml must exist for deployment"

        content = config_path.read_text(encoding="utf-8")
        assert "[theme]" in content
        assert "primaryColor" in content
        assert "[server]" in content
        assert "headless" in content

    def test_env_example_contains_all_required_keys(self):
        base_dir = Path(__file__).resolve().parent.parent
        env_example = base_dir / ".env.example"
        assert env_example.exists()

        content = env_example.read_text(encoding="utf-8")
        assert "MONGODB_URI" in content
        assert "MONGODB_DATABASE" in content
        assert "NEO4J_URI" in content
        assert "NEO4J_USERNAME" in content
        assert "NEO4J_PASSWORD" in content

    def test_gitignore_protects_secrets_and_large_files(self):
        base_dir = Path(__file__).resolve().parent.parent
        gitignore = base_dir / ".gitignore"
        assert gitignore.exists()

        lines = [line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()]
        assert ".env" in lines
        assert "venv/" in lines
        assert "data/raw/" in lines

    def test_validate_config_helper(self):
        # When environment variables are set or unset, returns structured dictionary
        res = validate_config()
        assert "mongodb_ok" in res
        assert "neo4j_ok" in res
        assert "issues" in res
        assert isinstance(res["issues"], list)
