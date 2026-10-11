"""
data_pipeline/clean_data.py
────────────────────────────
Streaming, memory-efficient data cleaning pipeline for the Yelp Open Dataset.

Key features:
1. Streams multi-gigabyte JSON/JSONL files line by line (generator-based, low memory).
2. Filters restaurant and food-related businesses while discarding unrelated businesses.
3. Normalizes categories into clean, trimmed, deduplicated lists and strings.
4. Robust error handling for malformed JSON lines, missing fields, and duplicate IDs.
5. Enforces referential integrity:
     - Reviews only retained if their business_id exists in the cleaned restaurant set.
     - Users only retained if their user_id wrote a retained review.
6. Exports both streaming JSONL (for MongoDB Atlas) and CSV (for Neo4j graph imports).
7. Produces an edge list CSV (restaurant_categories.csv) for Neo4j BELONGS_TO relationships.
8. Distinguishes synthetic test data from real Yelp data ('is_synthetic' flag preserved).
9. Generates a comprehensive data_quality_report.json with statistics and metrics.

Usage:
    python data_pipeline/clean_data.py --input-dir data/raw --output-dir data/processed --sample-size 500
    python data_pipeline/clean_data.py --test-data --sample-size 50
"""

import os
import sys
import csv
import json
import gzip
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterator, TextIO

# Configure sys.path so the script can be invoked from any directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Configure UTF-8 stdout for Windows PowerShell compatibility
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tastetrail.cleaner")

# Keywords used to identify restaurant & food establishments
RESTAURANT_KEYWORDS = {
    "restaurant", "restaurants", "food", "cafes", "cafe", "coffee & tea",
    "coffee", "tea", "bars", "bar", "bakeries", "bakery", "diners", "diner",
    "bistro", "bistros", "pubs", "pub", "pizzas", "pizza", "pizzerias",
    "gastropubs", "desserts", "ice cream & frozen yogurt", "fast food",
    "sandwiches", "sandwich", "delis", "deli", "breakfast & brunch", "brunch",
    "steakhouses", "steakhouse", "seafood", "barbeque", "bbq", "buffets",
    "breweries", "brewery", "tacos", "noodles", "burgers", "burger",
    "sushi bars", "sushi", "ramen", "italian", "chinese", "mexican",
    "japanese", "thai", "indian", "mediterranean", "american (traditional)",
    "american (new)", "vietnamese", "korean", "caribbean", "french", "greek",
}


def find_file(input_dir: Path, candidates: list[str]) -> Path | None:
    """Find the first matching file name in input_dir (case-insensitive)."""
    for candidate in candidates:
        target = input_dir / candidate
        if target.is_file():
            return target
        # Also check for .gz version
        target_gz = input_dir / f"{candidate}.gz"
        if target_gz.is_file():
            return target_gz

    # Fallback: scan directory
    try:
        for f in input_dir.iterdir():
            if f.is_file():
                for c in candidates:
                    if c.lower() in f.name.lower():
                        return f
    except Exception:
        pass
    return None


def open_text_file(file_path: Path) -> TextIO:
    """Open standard or gzipped text file with UTF-8 encoding."""
    if file_path.suffix == ".gz":
        return gzip.open(file_path, "rt", encoding="utf-8", errors="replace")
    return open(file_path, "r", encoding="utf-8", errors="replace")


def line_reader(file_path: Path) -> Iterator[tuple[int, str]]:
    """Yield line numbers and line content without loading entire file."""
    with open_text_file(file_path) as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if line_str:
                yield idx, line_str


def is_restaurant(categories_raw: str | list | None) -> bool:
    """Check if the categories string/list contains any restaurant/food keyword."""
    if not categories_raw:
        return False

    if isinstance(categories_raw, list):
        categories_str = ", ".join(str(c) for c in categories_raw)
    else:
        categories_str = str(categories_raw)

    tokens = [cat.strip().lower() for cat in categories_str.split(",") if cat.strip()]
    for token in tokens:
        if token in RESTAURANT_KEYWORDS:
            return True
        for kw in RESTAURANT_KEYWORDS:
            if kw in token:
                return True
    return False


def normalize_categories(categories_raw: str | list | None) -> tuple[list[str], str]:
    """
    Normalize categories into:
      1. A deduplicated list of clean category strings.
      2. A clean comma-separated string.
    """
    if not categories_raw:
        return [], ""

    if isinstance(categories_raw, list):
        items = [str(c).strip() for c in categories_raw if str(c).strip()]
    else:
        items = [c.strip() for c in str(categories_raw).split(",") if c.strip()]

    # Deduplicate while preserving order
    seen = set()
    cleaned = []
    for item in items:
        # Title case standard categories if needed, but preserve original casing generally
        normalized_key = item.lower()
        if normalized_key not in seen:
            seen.add(normalized_key)
            cleaned.append(item)

    return cleaned, ", ".join(cleaned)


class DataCleaner:
    """Streaming cleaner and validator for Yelp Open Dataset."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        sample_size: int = 500,
        max_reviews: int = 15000,
        city_filter: str | None = None,
        min_stars: float = 0.0,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.sample_size = sample_size
        self.max_reviews = max_reviews
        self.city_filter = city_filter.strip().lower() if city_filter else None
        self.min_stars = min_stars

        self.stats = {
            "pipeline_start": "",
            "pipeline_end": "",
            "duration_seconds": 0.0,
            "data_source": "yelp_raw",
            "businesses": {
                "raw_lines": 0,
                "malformed_lines": 0,
                "non_restaurants_filtered": 0,
                "city_filtered": 0,
                "stars_filtered": 0,
                "duplicate_ids": 0,
                "retained": 0,
            },
            "reviews": {
                "raw_lines": 0,
                "malformed_lines": 0,
                "unmatched_business_skipped": 0,
                "duplicate_ids": 0,
                "retained": 0,
            },
            "users": {
                "raw_lines": 0,
                "malformed_lines": 0,
                "unmatched_user_skipped": 0,
                "duplicate_ids": 0,
                "retained": 0,
            },
            "output_files": {},
        }

        self.retained_business_ids: set[str] = set()
        self.retained_user_ids: set[str] = set()
        self.is_synthetic_detected: bool = False

    def clean_restaurants(self) -> Path:
        """
        Stream business.json, filter restaurants, clean fields, and write:
          - restaurants_clean.jsonl
          - restaurants_clean.csv
          - restaurant_categories.csv (for Neo4j graph relationships)
        """
        biz_candidates = ["yelp_academic_dataset_business.json", "business.json"]
        biz_path = find_file(self.input_dir, biz_candidates)
        if not biz_path:
            raise FileNotFoundError(
                f"Could not find business JSON file in {self.input_dir}. "
                f"Expected one of: {biz_candidates}"
            )

        logger.info("Streaming and cleaning businesses from: %s", biz_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        jsonl_path = self.output_dir / "restaurants_clean.jsonl"
        csv_path = self.output_dir / "restaurants_clean.csv"
        cat_csv_path = self.output_dir / "restaurant_categories.csv"

        csv_fields = [
            "business_id", "name", "address", "city", "state", "postal_code",
            "latitude", "longitude", "stars", "review_count", "is_open",
            "categories", "is_synthetic",
        ]

        seen_ids = set()
        count_retained = 0

        with (
            open(jsonl_path, "w", encoding="utf-8") as f_jsonl,
            open(csv_path, "w", encoding="utf-8", newline="") as f_csv,
            open(cat_csv_path, "w", encoding="utf-8", newline="") as f_cat_csv,
        ):
            csv_writer = csv.DictWriter(f_csv, fieldnames=csv_fields)
            csv_writer.writeheader()

            cat_writer = csv.writer(f_cat_csv)
            cat_writer.writerow(["business_id", "category"])

            for line_no, line in line_reader(biz_path):
                self.stats["businesses"]["raw_lines"] += 1
                try:
                    record = json.loads(line)
                except Exception:
                    self.stats["businesses"]["malformed_lines"] += 1
                    continue

                if record.get("is_synthetic") or str(record.get("business_id", "")).startswith("syn_"):
                    self.is_synthetic_detected = True

                biz_id = str(record.get("business_id", "")).strip()
                if not biz_id:
                    self.stats["businesses"]["malformed_lines"] += 1
                    continue

                if biz_id in seen_ids:
                    self.stats["businesses"]["duplicate_ids"] += 1
                    continue

                # Filter by restaurant categories
                raw_cats = record.get("categories")
                if not is_restaurant(raw_cats):
                    self.stats["businesses"]["non_restaurants_filtered"] += 1
                    continue

                # City filter if specified
                city = str(record.get("city", "")).strip()
                if self.city_filter and city.lower() != self.city_filter:
                    self.stats["businesses"]["city_filtered"] += 1
                    continue

                # Stars filter
                try:
                    stars = float(record.get("stars", 0.0))
                except (ValueError, TypeError):
                    stars = 0.0

                if stars < self.min_stars:
                    self.stats["businesses"]["stars_filtered"] += 1
                    continue

                # Clean fields
                cat_list, cat_str = normalize_categories(raw_cats)
                name = str(record.get("name", "Unknown Restaurant")).strip()
                address = str(record.get("address", "")).strip()
                state = str(record.get("state", "")).strip()
                postal_code = str(record.get("postal_code", "")).strip()

                try:
                    lat = float(record.get("latitude")) if record.get("latitude") is not None else None
                except (ValueError, TypeError):
                    lat = None

                try:
                    lon = float(record.get("longitude")) if record.get("longitude") is not None else None
                except (ValueError, TypeError):
                    lon = None

                try:
                    review_count = int(record.get("review_count", 0))
                except (ValueError, TypeError):
                    review_count = 0

                is_open = int(record.get("is_open", 1))

                attributes = record.get("attributes")
                if not isinstance(attributes, dict):
                    attributes = {}

                hours = record.get("hours")
                if not isinstance(hours, dict):
                    hours = {}

                is_synthetic = bool(record.get("is_synthetic", False))

                clean_record = {
                    "business_id": biz_id,
                    "name": name,
                    "address": address,
                    "city": city,
                    "state": state,
                    "postal_code": postal_code,
                    "latitude": lat,
                    "longitude": lon,
                    "stars": round(stars, 1),
                    "review_count": max(0, review_count),
                    "is_open": is_open,
                    "categories": cat_list,
                    "categories_text": cat_str,
                    "attributes": attributes,
                    "hours": hours,
                    "is_synthetic": is_synthetic,
                }

                # Write JSONL
                f_jsonl.write(json.dumps(clean_record, ensure_ascii=False) + "\n")

                # Write CSV
                csv_writer.writerow({
                    "business_id": biz_id,
                    "name": name,
                    "address": address,
                    "city": city,
                    "state": state,
                    "postal_code": postal_code,
                    "latitude": lat if lat is not None else "",
                    "longitude": lon if lon is not None else "",
                    "stars": round(stars, 1),
                    "review_count": review_count,
                    "is_open": is_open,
                    "categories": cat_str,
                    "is_synthetic": is_synthetic,
                })

                # Write category edges
                for cat in cat_list:
                    cat_writer.writerow([biz_id, cat])

                seen_ids.add(biz_id)
                self.retained_business_ids.add(biz_id)
                count_retained += 1

                if self.sample_size > 0 and count_retained >= self.sample_size:
                    logger.info("Reached target sample size of %d restaurants.", self.sample_size)
                    break

        self.stats["businesses"]["retained"] = count_retained
        self.stats["output_files"]["restaurants_jsonl"] = str(jsonl_path)
        self.stats["output_files"]["restaurants_csv"] = str(csv_path)
        self.stats["output_files"]["restaurant_categories_csv"] = str(cat_csv_path)

        logger.info(
            "Restaurants cleaned: %d retained (out of %d raw lines)",
            count_retained, self.stats["businesses"]["raw_lines"]
        )
        return jsonl_path

    def clean_reviews(self) -> Path:
        """
        Stream review.json, keeping only reviews that reference retained restaurants.
        Writes:
          - reviews_clean.jsonl
          - reviews_clean.csv
        """
        rev_candidates = ["yelp_academic_dataset_review.json", "review.json"]
        rev_path = find_file(self.input_dir, rev_candidates)
        if not rev_path:
            raise FileNotFoundError(
                f"Could not find review JSON file in {self.input_dir}. "
                f"Expected one of: {rev_candidates}"
            )

        logger.info("Streaming and cleaning reviews from: %s", rev_path)

        jsonl_path = self.output_dir / "reviews_clean.jsonl"
        csv_path = self.output_dir / "reviews_clean.csv"

        csv_fields = [
            "review_id", "user_id", "business_id", "stars", "date",
            "useful", "funny", "cool", "is_synthetic",
        ]

        seen_rev_ids = set()
        count_retained = 0

        with (
            open(jsonl_path, "w", encoding="utf-8") as f_jsonl,
            open(csv_path, "w", encoding="utf-8", newline="") as f_csv,
        ):
            csv_writer = csv.DictWriter(f_csv, fieldnames=csv_fields)
            csv_writer.writeheader()

            for line_no, line in line_reader(rev_path):
                self.stats["reviews"]["raw_lines"] += 1
                try:
                    record = json.loads(line)
                except Exception:
                    self.stats["reviews"]["malformed_lines"] += 1
                    continue

                biz_id = str(record.get("business_id", "")).strip()
                if biz_id not in self.retained_business_ids:
                    self.stats["reviews"]["unmatched_business_skipped"] += 1
                    continue

                rev_id = str(record.get("review_id", "")).strip()
                if not rev_id:
                    self.stats["reviews"]["malformed_lines"] += 1
                    continue

                if rev_id in seen_rev_ids:
                    self.stats["reviews"]["duplicate_ids"] += 1
                    continue

                user_id = str(record.get("user_id", "")).strip()
                if not user_id:
                    self.stats["reviews"]["malformed_lines"] += 1
                    continue

                try:
                    stars = float(record.get("stars", 1.0))
                except (ValueError, TypeError):
                    stars = 1.0
                stars = max(1.0, min(5.0, stars))

                text = str(record.get("text", "")).strip()
                date_str = str(record.get("date", "")).strip()
                if not date_str:
                    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                try:
                    useful = int(record.get("useful", 0))
                    funny = int(record.get("funny", 0))
                    cool = int(record.get("cool", 0))
                except (ValueError, TypeError):
                    useful, funny, cool = 0, 0, 0

                is_synthetic = bool(record.get("is_synthetic", False))

                clean_record = {
                    "review_id": rev_id,
                    "user_id": user_id,
                    "business_id": biz_id,
                    "stars": round(stars, 1),
                    "text": text,
                    "date": date_str,
                    "useful": max(0, useful),
                    "funny": max(0, funny),
                    "cool": max(0, cool),
                    "is_synthetic": is_synthetic,
                }

                f_jsonl.write(json.dumps(clean_record, ensure_ascii=False) + "\n")
                csv_writer.writerow({
                    "review_id": rev_id,
                    "user_id": user_id,
                    "business_id": biz_id,
                    "stars": round(stars, 1),
                    "date": date_str,
                    "useful": max(0, useful),
                    "funny": max(0, funny),
                    "cool": max(0, cool),
                    "is_synthetic": is_synthetic,
                })

                seen_rev_ids.add(rev_id)
                self.retained_user_ids.add(user_id)
                count_retained += 1

                if self.max_reviews > 0 and count_retained >= self.max_reviews:
                    logger.info("Reached target maximum reviews limit of %d.", self.max_reviews)
                    break

        self.stats["reviews"]["retained"] = count_retained
        self.stats["output_files"]["reviews_jsonl"] = str(jsonl_path)
        self.stats["output_files"]["reviews_csv"] = str(csv_path)

        logger.info(
            "Reviews cleaned: %d retained (referencing %d unique users and %d businesses)",
            count_retained, len(self.retained_user_ids), len(self.retained_business_ids)
        )
        return jsonl_path

    def clean_users(self) -> Path:
        """
        Stream user.json, keeping only users who authored retained reviews.
        Writes:
          - users_clean.jsonl
          - users_clean.csv
        """
        user_candidates = ["yelp_academic_dataset_user.json", "user.json"]
        user_path = find_file(self.input_dir, user_candidates)
        if not user_path:
            logger.warning(
                "User JSON file not found in %s. Creating synthetic user stubs for retained reviewers.",
                self.input_dir
            )
            return self._create_user_stubs()

        logger.info("Streaming and cleaning users from: %s", user_path)

        jsonl_path = self.output_dir / "users_clean.jsonl"
        csv_path = self.output_dir / "users_clean.csv"

        csv_fields = [
            "user_id", "name", "review_count", "yelping_since",
            "average_stars", "useful", "funny", "cool", "fans", "is_synthetic",
        ]

        seen_user_ids = set()
        count_retained = 0

        with (
            open(jsonl_path, "w", encoding="utf-8") as f_jsonl,
            open(csv_path, "w", encoding="utf-8", newline="") as f_csv,
        ):
            csv_writer = csv.DictWriter(f_csv, fieldnames=csv_fields)
            csv_writer.writeheader()

            for line_no, line in line_reader(user_path):
                self.stats["users"]["raw_lines"] += 1
                try:
                    record = json.loads(line)
                except Exception:
                    self.stats["users"]["malformed_lines"] += 1
                    continue

                user_id = str(record.get("user_id", "")).strip()
                if user_id not in self.retained_user_ids:
                    self.stats["users"]["unmatched_user_skipped"] += 1
                    continue

                if user_id in seen_user_ids:
                    self.stats["users"]["duplicate_ids"] += 1
                    continue

                name = str(record.get("name", "Yelp Reviewer")).strip()
                yelping_since = str(record.get("yelping_since", "2020-01-01 00:00:00")).strip()

                try:
                    review_count = int(record.get("review_count", 1))
                    avg_stars = float(record.get("average_stars", 3.5))
                    useful = int(record.get("useful", 0))
                    funny = int(record.get("funny", 0))
                    cool = int(record.get("cool", 0))
                    fans = int(record.get("fans", 0))
                except (ValueError, TypeError):
                    review_count, avg_stars, useful, funny, cool, fans = 1, 3.5, 0, 0, 0, 0

                is_synthetic = bool(record.get("is_synthetic", False))

                clean_record = {
                    "user_id": user_id,
                    "name": name,
                    "review_count": max(1, review_count),
                    "yelping_since": yelping_since,
                    "average_stars": round(avg_stars, 2),
                    "useful": max(0, useful),
                    "funny": max(0, funny),
                    "cool": max(0, cool),
                    "fans": max(0, fans),
                    "is_synthetic": is_synthetic,
                }

                f_jsonl.write(json.dumps(clean_record, ensure_ascii=False) + "\n")
                csv_writer.writerow(clean_record)

                seen_user_ids.add(user_id)
                count_retained += 1

                # If all retained user_ids are found, we can stop streaming user.json
                if len(seen_user_ids) >= len(self.retained_user_ids):
                    logger.info("Found all %d retained user records in user.json", len(seen_user_ids))
                    break

        # Handle any retained user IDs not found in user.json (e.g. truncated dataset)
        missing_users = self.retained_user_ids - seen_user_ids
        if missing_users:
            logger.info("Generating inferred profiles for %d reviewers not present in user.json", len(missing_users))
            with (
                open(jsonl_path, "a", encoding="utf-8") as f_jsonl,
                open(csv_path, "a", encoding="utf-8", newline="") as f_csv,
            ):
                csv_writer = csv.DictWriter(f_csv, fieldnames=csv_fields)
                for missing_id in missing_users:
                    clean_record = {
                        "user_id": missing_id,
                        "name": f"Reviewer {missing_id[-4:]}",
                        "review_count": 1,
                        "yelping_since": "2022-01-01 00:00:00",
                        "average_stars": 4.0,
                        "useful": 0,
                        "funny": 0,
                        "cool": 0,
                        "fans": 0,
                        "is_synthetic": self.is_synthetic_detected,
                    }
                    f_jsonl.write(json.dumps(clean_record, ensure_ascii=False) + "\n")
                    csv_writer.writerow(clean_record)
                    count_retained += 1

        self.stats["users"]["retained"] = count_retained
        self.stats["output_files"]["users_jsonl"] = str(jsonl_path)
        self.stats["output_files"]["users_csv"] = str(csv_path)

        logger.info("Users cleaned: %d retained", count_retained)
        return jsonl_path

    def _create_user_stubs(self) -> Path:
        """Create user stubs if user.json was completely absent."""
        jsonl_path = self.output_dir / "users_clean.jsonl"
        csv_path = self.output_dir / "users_clean.csv"
        csv_fields = [
            "user_id", "name", "review_count", "yelping_since",
            "average_stars", "useful", "funny", "cool", "fans", "is_synthetic",
        ]
        with (
            open(jsonl_path, "w", encoding="utf-8") as f_jsonl,
            open(csv_path, "w", encoding="utf-8", newline="") as f_csv,
        ):
            csv_writer = csv.DictWriter(f_csv, fieldnames=csv_fields)
            csv_writer.writeheader()
            for uid in self.retained_user_ids:
                record = {
                    "user_id": uid,
                    "name": f"Reviewer {uid[-4:]}",
                    "review_count": 1,
                    "yelping_since": "2022-01-01 00:00:00",
                    "average_stars": 4.0,
                    "useful": 0,
                    "funny": 0,
                    "cool": 0,
                    "fans": 0,
                    "is_synthetic": self.is_synthetic_detected,
                }
                f_jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
                csv_writer.writerow(record)

        self.stats["users"]["retained"] = len(self.retained_user_ids)
        self.stats["output_files"]["users_jsonl"] = str(jsonl_path)
        self.stats["output_files"]["users_csv"] = str(csv_path)
        return jsonl_path

    def run(self) -> dict:
        """Run the full data cleaning pipeline."""
        start_time = time.time()
        self.stats["pipeline_start"] = datetime.now(timezone.utc).isoformat()

        self.clean_restaurants()
        self.clean_reviews()
        self.clean_users()

        end_time = time.time()
        self.stats["pipeline_end"] = datetime.now(timezone.utc).isoformat()
        self.stats["duration_seconds"] = round(end_time - start_time, 2)
        self.stats["data_source"] = "synthetic" if self.is_synthetic_detected else "yelp_raw"

        # Save data quality report
        report_file = self.output_dir / "data_quality_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)

        logger.info(
            "Data cleaning pipeline finished in %.2fs. Report saved to: %s",
            self.stats["duration_seconds"], report_file
        )
        return self.stats


def main():
    parser = argparse.ArgumentParser(
        description="Streaming Yelp Dataset Cleaner and Validator for TasteTrail."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="data/raw",
        help="Path to directory containing raw Yelp JSON files (default: data/raw)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="Path to directory for cleaned JSONL and CSV exports (default: data/processed)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=500,
        help="Maximum restaurant records to clean and retain (default: 500; 0 for all)",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=15000,
        help="Maximum reviews to retain (default: 15000; 0 for all)",
    )
    parser.add_argument(
        "--city",
        type=str,
        default=None,
        help="Filter restaurants by city name (optional)",
    )
    parser.add_argument(
        "--min-stars",
        type=float,
        default=0.0,
        help="Filter restaurants by minimum rating (default: 0.0)",
    )
    parser.add_argument(
        "--test-data",
        action="store_true",
        help="Run generator first to produce synthetic test data in data/sample_raw and clean it",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if args.test_data:
        from data_pipeline.generate_sample_data import generate_synthetic_dataset
        sample_raw_dir = Path("data/sample_raw")
        logger.info("Generating synthetic test dataset in %s...", sample_raw_dir)
        generate_synthetic_dataset(
            output_dir=sample_raw_dir,
            num_restaurants=max(40, min(args.sample_size, 100)),
            num_other_businesses=10,
            num_users=60,
            reviews_per_restaurant=6,
        )
        input_dir = sample_raw_dir
        if output_dir == Path("data/processed"):
            output_dir = Path("data/sample_processed")

    cleaner = DataCleaner(
        input_dir=input_dir,
        output_dir=output_dir,
        sample_size=args.sample_size,
        max_reviews=args.max_reviews,
        city_filter=args.city,
        min_stars=args.min_stars,
    )
    cleaner.run()


if __name__ == "__main__":
    main()
