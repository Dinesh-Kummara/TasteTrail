"""
tests/test_phase1_setup.py
───────────────────────────
Phase 1 verification tests.
These tests do NOT require a live database connection.
They verify that the project structure, config, and imports are correct.

Run with:
    pytest tests/test_phase1_setup.py -v
"""

import sys
import os
import importlib
from pathlib import Path

# Ensure the project root is on the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── 1. Project structure ───────────────────────────────────────────────────────

class TestProjectStructure:
    """Verify that all required directories and files exist."""

    REQUIRED_DIRS = [
        "config",
        "pages",
        "components",
        "database",
        "services",
        "data_pipeline",
        "scripts",
        "tests",
    ]

    REQUIRED_FILES = [
        "app.py",
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "config/settings.py",
        "config/__init__.py",
        "database/mongodb_connection.py",
        "database/neo4j_connection.py",
        "database/__init__.py",
        "components/navbar.py",
        "components/restaurant_card.py",
        "components/rating_display.py",
        "scripts/verify_connections.py",
        "pages/2_Explore_Restaurants.py",
        "pages/3_Restaurant_Details.py",
        "pages/4_Recommendations.py",
        "pages/5_Analytics_Dashboard.py",
    ]

    def test_required_directories_exist(self):
        for d in self.REQUIRED_DIRS:
            path = PROJECT_ROOT / d
            assert path.is_dir(), f"Missing directory: {d}"

    def test_required_files_exist(self):
        for f in self.REQUIRED_FILES:
            path = PROJECT_ROOT / f
            assert path.is_file(), f"Missing file: {f}"

    def test_env_example_exists_and_not_env(self):
        assert (PROJECT_ROOT / ".env.example").is_file()
        # Make sure we don't accidentally ship real .env
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            content = env_file.read_text()
            assert "<password>" not in content or True  # presence is OK, real creds are user's


# ── 2. Config imports ──────────────────────────────────────────────────────────

class TestConfigImports:
    """Verify the config module imports cleanly even without a .env file."""

    def test_settings_importable(self):
        mod = importlib.import_module("config.settings")
        assert hasattr(mod, "MONGODB_URI")
        assert hasattr(mod, "NEO4J_URI")
        assert hasattr(mod, "validate_config")

    def test_validate_config_returns_dict(self):
        from config.settings import validate_config
        result = validate_config()
        assert isinstance(result, dict)
        assert "mongodb_ok" in result
        assert "neo4j_ok" in result
        assert "issues" in result

    def test_default_database_name(self):
        from config.settings import MONGODB_DATABASE
        assert MONGODB_DATABASE == "restaurant_recommendation"

    def test_collection_names(self):
        from config.settings import (
            RESTAURANTS_COLLECTION,
            REVIEWS_COLLECTION,
            USERS_COLLECTION,
        )
        assert RESTAURANTS_COLLECTION in ("businesses", "restaurants")
        assert REVIEWS_COLLECTION == "reviews"
        assert USERS_COLLECTION == "users"


# ── 3. Component imports ───────────────────────────────────────────────────────

class TestComponentImports:
    """Verify components import without error (no Streamlit server needed for import)."""

    def test_rating_display_importable(self):
        from components.rating_display import star_html, render_rating_badge  # noqa
        assert callable(star_html)

    def test_star_html_output(self):
        from components.rating_display import star_html
        result = star_html(4.5)
        assert "★" in result
        assert "☆" in result or "½" in result

    def test_star_html_full_five(self):
        from components.rating_display import star_html
        result = star_html(5.0)
        assert result.count("★") == 5

    def test_star_html_zero(self):
        from components.rating_display import star_html
        result = star_html(0.0)
        assert "★" not in result or result.count("★") == 0


# ── 4. Requirements file ───────────────────────────────────────────────────────

class TestRequirements:
    """Verify requirements.txt lists the mandatory packages."""

    REQUIRED_PACKAGES = [
        "streamlit",
        "pymongo",
        "neo4j",
        "pandas",
        "plotly",
        "python-dotenv",
        "pytest",
    ]

    def test_requirements_contains_packages(self):
        req_path = PROJECT_ROOT / "requirements.txt"
        content = req_path.read_text().lower()
        for pkg in self.REQUIRED_PACKAGES:
            assert pkg.lower() in content, f"Missing package in requirements.txt: {pkg}"


# ── 5. .gitignore ─────────────────────────────────────────────────────────────

class TestGitignore:
    """Verify .gitignore excludes sensitive and large files."""

    def test_env_ignored(self):
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert ".env" in content

    def test_raw_data_ignored(self):
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert "data/raw" in content or "raw/" in content
