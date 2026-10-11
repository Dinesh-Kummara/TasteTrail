"""
tests/test_data_validation.py
──────────────────────────────
Phase 2 test suite:
  - Synthetic dataset generation (schema adherence, synthetic labeling)
  - Category normalization and restaurant keyword filtering
  - Streaming cleaner: malformed JSON tolerance, duplicate ID skipping
  - Referential integrity: reviews -> restaurants, users -> reviews
  - CSV and JSONL export validity
  - Data quality report structure
"""

import json
import csv
from pathlib import Path
import pytest

from data_pipeline.generate_sample_data import generate_synthetic_dataset
from data_pipeline.clean_data import (
    is_restaurant,
    normalize_categories,
    DataCleaner,
)


class TestCategoryAndFiltering:
    """Tests for business classification and category normalization."""

    def test_is_restaurant_positive(self):
        assert is_restaurant("Restaurants, Italian, Pizza") is True
        assert is_restaurant("Food, Bakeries, Coffee & Tea") is True
        assert is_restaurant("Bars, Nightlife, Gastropubs") is True
        assert is_restaurant(["Burgers", "Fast Food"]) is True

    def test_is_restaurant_negative(self):
        assert is_restaurant("Automotive, Auto Repair, Oil Change") is False
        assert is_restaurant("Health & Medical, Dentists") is False
        assert is_restaurant("Dry Cleaning & Laundry, Local Services") is False
        assert is_restaurant("") is False
        assert is_restaurant(None) is False

    def test_normalize_categories(self):
        cats_list, cats_str = normalize_categories("  Italian, Pizza , Italian, Bars  ")
        assert cats_list == ["Italian", "Pizza", "Bars"]
        assert cats_str == "Italian, Pizza, Bars"

    def test_normalize_categories_empty_or_none(self):
        assert normalize_categories(None) == ([], "")
        assert normalize_categories("") == ([], "")


class TestSyntheticDataGeneration:
    """Tests for synthetic Yelp dataset generation."""

    @pytest.fixture
    def sample_dir(self, tmp_path):
        out_dir = tmp_path / "synthetic_test"
        generate_synthetic_dataset(
            output_dir=out_dir,
            num_restaurants=10,
            num_other_businesses=3,
            num_users=15,
            reviews_per_restaurant=4,
            seed=123,
        )
        return out_dir

    def test_files_created(self, sample_dir):
        assert (sample_dir / "business.json").exists()
        assert (sample_dir / "user.json").exists()
        assert (sample_dir / "review.json").exists()
        assert (sample_dir / "sample_manifest.json").exists()

    def test_schema_and_synthetic_flag(self, sample_dir):
        # Verify businesses
        with open(sample_dir / "business.json", "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
            assert len(lines) == 13  # 10 restaurants + 3 non-restaurants
            for b in lines:
                assert b["is_synthetic"] is True
                assert b["business_id"].startswith("syn_b_")
                assert "stars" in b
                assert "city" in b

        # Verify users
        with open(sample_dir / "user.json", "r", encoding="utf-8") as f:
            users = [json.loads(line) for line in f]
            assert len(users) == 15
            for u in users:
                assert u["is_synthetic"] is True
                assert u["user_id"].startswith("syn_u_")

        # Verify reviews
        with open(sample_dir / "review.json", "r", encoding="utf-8") as f:
            reviews = [json.loads(line) for line in f]
            assert len(reviews) > 0
            for r in reviews:
                assert r["is_synthetic"] is True
                assert r["review_id"].startswith("syn_r_")
                assert 1.0 <= r["stars"] <= 5.0


class TestDataCleaningPipeline:
    """Tests for streaming cleaner, filtering, deduplication, and referential integrity."""

    @pytest.fixture
    def pipeline_setup(self, tmp_path):
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"

        # Generate 15 restaurants and 5 non-restaurants
        generate_synthetic_dataset(
            output_dir=raw_dir,
            num_restaurants=15,
            num_other_businesses=5,
            num_users=20,
            reviews_per_restaurant=3,
            seed=99,
        )

        cleaner = DataCleaner(
            input_dir=raw_dir,
            output_dir=processed_dir,
            sample_size=0,  # 0 means process all records
            max_reviews=50,
        )
        stats = cleaner.run()
        return raw_dir, processed_dir, stats

    def test_non_restaurants_are_filtered_out(self, pipeline_setup):
        _, _, stats = pipeline_setup
        assert stats["businesses"]["raw_lines"] == 20
        assert stats["businesses"]["non_restaurants_filtered"] == 5
        assert stats["businesses"]["retained"] == 15

    def test_referential_integrity(self, pipeline_setup):
        _, processed_dir, _ = pipeline_setup

        # Load retained restaurant IDs
        retained_biz_ids = set()
        with open(processed_dir / "restaurants_clean.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                retained_biz_ids.add(rec["business_id"])

        # Load retained user IDs
        retained_user_ids = set()
        with open(processed_dir / "users_clean.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                retained_user_ids.add(rec["user_id"])

        # Check every review points to a retained restaurant and user
        with open(processed_dir / "reviews_clean.jsonl", "r", encoding="utf-8") as f:
            review_count = 0
            for line in f:
                rev = json.loads(line)
                assert rev["business_id"] in retained_biz_ids, "Orphaned review found!"
                assert rev["user_id"] in retained_user_ids, "Review references unindexed user!"
                review_count += 1
            assert review_count > 0

    def test_csv_and_edge_list_files(self, pipeline_setup):
        _, processed_dir, _ = pipeline_setup
        assert (processed_dir / "restaurants_clean.csv").exists()
        assert (processed_dir / "reviews_clean.csv").exists()
        assert (processed_dir / "users_clean.csv").exists()
        assert (processed_dir / "restaurant_categories.csv").exists()

        # Check category edge list has valid header and records
        with open(processed_dir / "restaurant_categories.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["business_id", "category"]
            rows = list(reader)
            assert len(rows) > 0

    def test_data_quality_report_structure(self, pipeline_setup):
        _, processed_dir, stats = pipeline_setup
        report_path = processed_dir / "data_quality_report.json"
        assert report_path.exists()

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert report["data_source"] == "synthetic"
        assert report["businesses"]["retained"] == 15
        assert "restaurants_jsonl" in report["output_files"]
        assert "reviews_jsonl" in report["output_files"]
        assert "users_jsonl" in report["output_files"]

    def test_sample_size_truncation(self, tmp_path):
        raw_dir = tmp_path / "raw_trunc"
        processed_dir = tmp_path / "proc_trunc"
        generate_synthetic_dataset(
            output_dir=raw_dir,
            num_restaurants=20,
            num_other_businesses=2,
            num_users=10,
            reviews_per_restaurant=2,
            seed=42,
        )
        cleaner = DataCleaner(
            input_dir=raw_dir,
            output_dir=processed_dir,
            sample_size=5,
        )
        stats = cleaner.run()
        assert stats["businesses"]["retained"] == 5


class TestMalformedAndDuplicateTolerance:
    """Test cleaner resilience against dirty data."""

    def test_malformed_lines_and_duplicates_handled(self, tmp_path):
        raw_dir = tmp_path / "dirty_raw"
        out_dir = tmp_path / "dirty_out"
        raw_dir.mkdir()

        # Create business.json with duplicates, malformed json, non-restaurant
        biz_file = raw_dir / "business.json"
        with open(biz_file, "w", encoding="utf-8") as f:
            f.write("MALFORMED JSON LINE 1234\n")
            f.write(json.dumps({
                "business_id": "b1",
                "name": "Pizza Corner",
                "categories": "Restaurants, Pizza",
                "stars": 4.5,
                "city": "Philly"
            }) + "\n")
            # Duplicate b1
            f.write(json.dumps({
                "business_id": "b1",
                "name": "Duplicate Pizza",
                "categories": "Restaurants, Pizza",
                "stars": 4.0,
                "city": "Philly"
            }) + "\n")
            # Non-restaurant
            f.write(json.dumps({
                "business_id": "b2",
                "name": "Car Wash",
                "categories": "Automotive",
                "stars": 3.0,
                "city": "Philly"
            }) + "\n")

        # Create review.json referencing b1 and unknown b99
        rev_file = raw_dir / "review.json"
        with open(rev_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "review_id": "r1",
                "business_id": "b1",
                "user_id": "u1",
                "stars": 5.0,
                "text": "Great!"
            }) + "\n")
            # Duplicate r1
            f.write(json.dumps({
                "review_id": "r1",
                "business_id": "b1",
                "user_id": "u1",
                "stars": 5.0,
                "text": "Great!"
            }) + "\n")
            # Orphan review referencing b99 (not retained)
            f.write(json.dumps({
                "review_id": "r2",
                "business_id": "b99",
                "user_id": "u2",
                "stars": 2.0,
                "text": "Bad!"
            }) + "\n")

        cleaner = DataCleaner(input_dir=raw_dir, output_dir=out_dir)
        stats = cleaner.run()

        assert stats["businesses"]["malformed_lines"] == 1
        assert stats["businesses"]["duplicate_ids"] == 1
        assert stats["businesses"]["non_restaurants_filtered"] == 1
        assert stats["businesses"]["retained"] == 1  # Only b1

        assert stats["reviews"]["duplicate_ids"] == 1
        assert stats["reviews"]["unmatched_business_skipped"] == 1  # b99 skipped
        assert stats["reviews"]["retained"] == 1  # Only r1
