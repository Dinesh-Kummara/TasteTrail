# TasteTrail – Data Pipeline (Phase 2)

This directory contains the streaming, memory-efficient data preparation and validation pipeline for the **TasteTrail** Restaurant Review and Recommendation System.

---

## 1. Overview of Scripts

| Script | Purpose |
|---|---|
| `data_pipeline/generate_sample_data.py` | Generates realistic, schema-accurate synthetic Yelp dataset files for testing when the 10+ GB Yelp Open Dataset is not available. Explicitly labels records with `is_synthetic: true` and `syn_` prefixes. |
| `data_pipeline/clean_data.py` | Production-grade streaming data cleaner. Reads large Yelp JSON files line-by-line, filters food/restaurant businesses, normalizes categories, eliminates duplicates/orphans, and outputs clean JSONL & CSV files. |

---

## 2. Key Pipeline Capabilities

1. **Streaming Execution**: Yelp Open Dataset files (`review.json` is ~5.3 GB, `user.json` is ~3 GB) are processed line by line via generators. Memory consumption remains strictly bounded regardless of dataset size.
2. **Flexible File Discovery**: Automatically detects standard filenames (`yelp_academic_dataset_business.json` or `business.json`), as well as `.json.gz` compressed archives.
3. **Restaurant Classification**: Filters businesses against a curated set of restaurant, dining, bar, cafe, and food keywords. Discards non-food establishments (e.g., auto repair, dentists, salons).
4. **Category Normalization**: Converts raw comma-delimited category strings into deduplicated, clean Python lists and strings.
5. **Referential Integrity Enforcement**:
   - Only reviews referencing retained restaurants are kept.
   - Only users who authored retained reviews are kept.
6. **Multi-Format Export**:
   - **JSONL** (`restaurants_clean.jsonl`, `reviews_clean.jsonl`, `users_clean.jsonl`): Ready for batch insertion into MongoDB Atlas.
   - **CSV** (`restaurants_clean.csv`, `reviews_clean.csv`, `users_clean.csv`): Ready for relational exploration or Neo4j Aura `LOAD CSV`.
   - **Graph Edge List** (`restaurant_categories.csv`): Formatted pair list (`business_id,category`) for easy Neo4j `(r:Restaurant)-[:BELONGS_TO]->(c:Category)` relationship imports.
7. **Quality Audit & Statistics**: Automatically writes `data_quality_report.json` logging retained records, filtered counts, malformed lines, and timings.

---

## 3. PowerShell Commands

### Option A: Clean Real Yelp Open Dataset Files

Place your downloaded Yelp files (`business.json`, `review.json`, `user.json`) inside `data/raw/`:

```powershell
# Clean with a sample size of 500 restaurants:
.\venv\Scripts\python.exe data_pipeline/clean_data.py --input-dir data/raw --output-dir data/processed --sample-size 500

# Clean with all restaurants (no sample limit):
.\venv\Scripts\python.exe data_pipeline/clean_data.py --input-dir data/raw --output-dir data/processed --sample-size 0

# Filter specifically by city (e.g., Philadelphia):
.\venv\Scripts\python.exe data_pipeline/clean_data.py --input-dir data/raw --output-dir data/processed --city "Philadelphia" --sample-size 300
```

### Option B: Test Data Mode (Self-Contained)

If you have not downloaded the 10+ GB Yelp dataset, generate realistic synthetic test data and clean it automatically:

```powershell
# One-step generate and clean synthetic data:
.\venv\Scripts\python.exe data_pipeline/clean_data.py --test-data --sample-size 50
```

Or run the synthetic generator manually:

```powershell
.\venv\Scripts\python.exe data_pipeline/generate_sample_data.py --output-dir data/sample_raw --num-restaurants 60 --num-other-businesses 10 --num-users 80 --reviews-per-restaurant 6
```

---

## 4. Command-Line Arguments Reference

### `data_pipeline/clean_data.py`

| Flag | Default | Description |
|---|---|---|
| `--input-dir` | `data/raw` | Path to directory containing raw JSON files |
| `--output-dir` | `data/processed` | Destination directory for clean JSONL and CSV files |
| `--sample-size` | `500` | Maximum number of restaurants to clean and retain (`0` for all) |
| `--max-reviews` | `15000` | Maximum reviews to retain (`0` for all) |
| `--city` | `None` | Optional case-insensitive city filter (e.g. `Philadelphia`) |
| `--min-stars` | `0.0` | Minimum restaurant star rating filter |
| `--test-data` | `False` | Automatically generates synthetic data in `data/sample_raw` and cleans it to `data/sample_processed` |

### `data_pipeline/generate_sample_data.py`

| Flag | Default | Description |
|---|---|---|
| `--output-dir` | `data/sample_raw` | Target directory for generated raw sample files |
| `--num-restaurants` | `50` | Number of restaurant businesses to generate |
| `--num-other-businesses`| `10` | Number of non-food businesses for filter testing |
| `--num-users` | `80` | Number of users to generate |
| `--reviews-per-restaurant`| `6` | Average reviews per restaurant |
| `--seed` | `42` | Random seed for deterministic reproducibility |

---

## 5. Output Schemas

### `restaurants_clean.jsonl` (Document Model for MongoDB)
```json
{
  "business_id": "syn_b_0001",
  "name": "Bella Trattoria",
  "address": "412 Chestnut St",
  "city": "Philadelphia",
  "state": "PA",
  "postal_code": "19107",
  "latitude": 39.9526,
  "longitude": -75.1652,
  "stars": 4.5,
  "review_count": 182,
  "is_open": 1,
  "categories": ["Restaurants", "Italian", "Pizza", "Bars", "Wine Bars"],
  "categories_text": "Restaurants, Italian, Pizza, Bars, Wine Bars",
  "attributes": {
    "RestaurantsPriceRange2": "2",
    "OutdoorSeating": "True",
    "BusinessAcceptsCreditCards": "True"
  },
  "hours": {
    "Monday": "11:0-22:0"
  },
  "is_synthetic": true
}
```

### `restaurant_categories.csv` (Edge List for Neo4j)
```csv
business_id,category
syn_b_0001,Restaurants
syn_b_0001,Italian
syn_b_0001,Pizza
syn_b_0001,Bars
syn_b_0001,Wine Bars
```

---

## 6. Running Tests

Run the comprehensive data validation test suite:

```powershell
.\venv\Scripts\pytest tests/test_data_validation.py -v
```
