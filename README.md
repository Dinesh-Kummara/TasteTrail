# 🍽️ TasteTrail – Restaurant Review and Recommendation System

> **Discover places worth tasting.**  
> An academic database engineering project using the Yelp Open Dataset,  
> MongoDB Atlas (document store), and Neo4j Aura (graph database).

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Database Setup](#database-setup)
6. [Dataset Preparation](#dataset-preparation)
7. [Data Import](#data-import)
8. [Running the Application](#running-the-application)
9. [Testing](#testing)
10. [Deployment](#deployment)
11. [Screenshots](#screenshots)
12. [Limitations](#limitations)

---

## Project Overview

TasteTrail is a full-stack restaurant discovery and recommendation platform.
It demonstrates:

- **Document-oriented data modelling** in MongoDB (restaurant profiles, reviews, users)
- **Graph-based relationship queries** in Neo4j (user–restaurant–category relationships)
- **Combined recommendation engine** using category similarity and graph traversal
- **Interactive analytics dashboard** with Plotly charts

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web Framework | Streamlit 1.35 |
| Document DB | MongoDB Atlas |
| Graph DB | Neo4j Aura |
| DB Drivers | PyMongo 4.7, neo4j 5.20 |
| Data Processing | Pandas 2.2 |
| Visualisation | Plotly 5.22 |
| Config | python-dotenv 1.0 |

---

## Project Structure

```
restaurant-recommendation-system/
├── app.py                          # Entry point + Home page
├── requirements.txt                # Pinned production dependencies
├── .env.example                    # Credential template (safe to commit)
├── .gitignore                      # Git exclusion rules
├── README.md                       # Comprehensive documentation
├── .streamlit/
│   └── config.toml                 # Production theme and server configuration
├── config/
│   ├── __init__.py
│   └── settings.py                 # Environment variables, timeouts, constants
├── pages/
│   ├── 2_Explore_Restaurants.py    # Search, multi-criteria filters, pagination
│   ├── 3_Restaurant_Details.py     # Profile, star breakdown, reviews, graph links
│   ├── 4_Recommendations.py       # Similarity and Bayesian discovery engine
│   └── 5_Analytics_Dashboard.py    # Plotly intelligence, live KPIs, CSV exports
├── components/
│   ├── navbar.py                   # Global CSS injection & sidebar brand
│   ├── restaurant_card.py          # Reusable styled restaurant card component
│   ├── rating_display.py           # Star rating HTML renderer
│   └── search_filters.py           # Shared search and filter controls
├── database/
│   ├── mongodb_connection.py       # Cached MongoClient with graceful fallback
│   ├── neo4j_connection.py         # Cached Neo4j Driver with Aura TLS support
│   ├── mongodb_queries.py          # Filtered searches, rankings, aggregations
│   └── neo4j_queries.py            # Graph similarity, collaborative queries, metrics
├── services/
│   ├── recommendation_service.py   # Jaccard index, Bayesian rating, composite scores
│   └── analytics_service.py        # Plotly chart builders, KPI summaries, CSV exports
├── data_pipeline/
│   ├── clean_data.py               # Yelp JSON streaming, normalization, sampling
│   ├── generate_sample_data.py     # Deterministic synthetic data generator
│   ├── import_mongodb.py           # Bulk upsert importer for MongoDB Atlas
│   └── import_neo4j.py             # Parameterized UNWIND graph importer
├── scripts/
│   ├── verify_connections.py       # Dual-database connectivity verification
│   ├── create_indexes.py           # MongoDB index generator & verification
│   └── create_neo4j_constraints.py # Neo4j uniqueness constraints builder
└── tests/
    ├── test_phase1_setup.py
    ├── test_data_validation.py
    ├── test_mongodb_integration.py
    ├── test_neo4j_integration.py
    ├── test_phase5_ui.py
    ├── test_phase6_details.py
    ├── test_phase7_recommendations.py
    ├── test_recommendation_service.py
    ├── test_phase8_analytics.py
    └── test_phase9_e2e.py
```

---

## Installation

### Prerequisites

- Python 3.12 (download from [python.org](https://www.python.org/downloads/))
- Git
- VS Code (recommended)
- MongoDB Atlas account ([free tier](https://www.mongodb.com/cloud/atlas))
- Neo4j Aura account ([free tier](https://neo4j.com/cloud/aura-free/))

### Step 1 – Clone the repository

```bash
git clone https://github.com/<your-username>/tastetrail.git
cd tastetrail/restaurant-recommendation-system
```

### Step 2 – Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3 – Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 – Configure environment variables

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

Edit `.env` and fill in your MongoDB Atlas URI and Neo4j Aura credentials.

---

## Database Setup

### MongoDB Atlas

1. Create a free cluster at [MongoDB Atlas](https://cloud.mongodb.com).
2. Create a database user with read/write access.
3. Allow your IP address in Network Access.
4. Copy the connection string to `MONGODB_URI` in `.env`.

### Neo4j Aura

1. Create a free instance at [Neo4j Aura](https://console.neo4j.io).
2. Download the credentials file when the instance is created.
3. Copy the URI and password to `NEO4J_URI` and `NEO4J_PASSWORD` in `.env`.

---

## Dataset Preparation

1. Download the [Yelp Open Dataset](https://www.yelp.com/dataset).
2. Create the raw data directory:
   ```bash
   mkdir -p data/raw
   ```
3. Extract and place these files in `data/raw/`:
   - `yelp_academic_dataset_business.json`
   - `yelp_academic_dataset_review.json`
   - `yelp_academic_dataset_user.json`

4. Run the cleaning pipeline:
   ```powershell
   # Clean Yelp files with a sample of 500 restaurants:
   .\venv\Scripts\python.exe data_pipeline/clean_data.py --input-dir data/raw --output-dir data/processed --sample-size 500

   # Or generate and clean synthetic test data automatically:
   .\venv\Scripts\python.exe data_pipeline/clean_data.py --test-data --sample-size 50
   ```

---

## Data Import (MongoDB Atlas)

### 1. Configure Credentials
Ensure your MongoDB Atlas connection string is saved in `.env`:
```ini
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=restaurant_recommendation
```

### 2. Verify or Create Indexes
Run index management to build unique, compound, text, and multikey indexes safely:
```powershell
# Inspect existing indexes:
.\venv\Scripts\python.exe scripts/create_indexes.py --check-only

# Create and verify all required indexes:
.\venv\Scripts\python.exe scripts/create_indexes.py
```

### 3. Ingest Cleaned Data into MongoDB Atlas
Upsert records into `restaurants`, `reviews`, and `users` collections:
```powershell
# Ingest processed dataset:
.\venv\Scripts\python.exe data_pipeline/import_mongodb.py --data-dir data/processed --batch-size 500

# Or ingest sample processed data:
.\venv\Scripts\python.exe data_pipeline/import_mongodb.py --data-dir data/sample_processed --batch-size 500

# Dry-run mode (simulate without writing to database):
.\venv\Scripts\python.exe data_pipeline/import_mongodb.py --data-dir data/sample_processed --dry-run
```

---

## Data Import (Neo4j Aura Graph)

### 1. Configure Credentials
Set your Neo4j Aura connection details in `.env`:
```ini
NEO4J_URI=neo4j+s://<your-aura-instance>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-password>
NEO4J_DATABASE=neo4j
```

### 2. Create Uniqueness Constraints
Verify and apply schema constraints on unique identifiers:
```powershell
# Inspect constraints and graph health:
.\venv\Scripts\python.exe scripts/create_neo4j_constraints.py --check-only

# Create uniqueness constraints:
.\venv\Scripts\python.exe scripts/create_neo4j_constraints.py
```

### 3. Ingest Graph Nodes & Relationships
Stream cleaned data into Neo4j Aura using parameterized `UNWIND` Cypher batches:
```powershell
# Ingest processed dataset:
.\venv\Scripts\python.exe data_pipeline/import_neo4j.py --data-dir data/processed --batch-size 500

# Or ingest sample processed data:
.\venv\Scripts\python.exe data_pipeline/import_neo4j.py --data-dir data/sample_processed --batch-size 500

# Dry-run mode (simulate without writing to Neo4j):
.\venv\Scripts\python.exe data_pipeline/import_neo4j.py --data-dir data/sample_processed --dry-run
```

---

## Running the Application

### Verify database connections first:
```powershell
.\venv\Scripts\python.exe scripts/verify_connections.py
```

### Start the Streamlit application:
```powershell
.\venv\Scripts\streamlit run app.py
```

The app opens automatically at **http://localhost:8501**

---

---

## Recommendation Engine (Phase 7)

TasteTrail features an intelligent, multi-criteria recommendation engine independent of the presentation layer, located in `services/recommendation_service.py`.

### 1. Mathematical Models & Formulas

#### Category Similarity (Jaccard Index)
Quantifies cuisine overlap between reference venue $A$ and candidate venue $B$:
$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
- Standardizes diverse category formats (lists, comma-delimited strings) into trimmed, lowercased sets.
- Safely handles empty or missing category profiles without division by zero ($J = 0.0$).

#### Bayesian Rating Adjustment (Shrinkage Prior)
Penalizes high star ratings backed by very few reviews, shrinking volatile ratings toward the candidate pool consensus:
$$BR = \left(\frac{v}{v + m}\right) R + \left(\frac{m}{v + m}\right) C$$
- $R$: Average restaurant rating from the historical Yelp business record.
- $v$: Historical review count.
- $C$: Average rating across the relevant candidate dataset (baseline prior).
- $m$: Minimum review confidence threshold (default: $10$).
- When $v = 0$, $BR = C$ (reverts to dataset baseline).
- High review counts ($v \gg m$) preserve authentic high ratings ($BR \approx R$).

#### Composite Recommendation Score
Combines content similarity and Bayesian quality into a transparent 100-point scale:
$$\text{Score} = 100 \times \left(w_{\text{category}} \cdot J(A, B) + w_{\text{rating}} \cdot \frac{BR}{5.0}\right)$$
- Default weights: $w_{\text{category}} = 0.6$ ($60\%$), $w_{\text{rating}} = 0.4$ ($40\%$).
- Weights are validated to be non-negative and normalized so $w_{\text{category}} + w_{\text{rating}} = 1.0$.
- In general discovery mode (without a reference restaurant), ranking is driven purely by Bayesian consensus without fabricating personal affinity.

#### Deterministic Tie-Breaking
When candidates achieve identical scores, rankings are deterministically resolved by:
1. `is_same_city` (prioritizes local neighborhood venues if requested)
2. `review_count` (higher review volume)
3. `business_id` (lexicographical stability)

### 2. Multi-Criteria Filtering
- **City / Region:** Restricts candidates to a selected municipality or searches globally.
- **Cuisine / Category:** Pre-filters candidates by specific cuisine.
- **Minimum Rating Threshold:** Ignores venues below specified star tiers.
- **Review Evidence:** Eliminates venues without sufficient review consensus.
- **Display Limit:** Configurable output size (6, 9, 12, 18).

### 3. Hybrid Neo4j Graph Integration & Graceful Fallback
- Reuses graph relationship queries (`get_collaborative_recommendations` and `get_similar_restaurants`) to inject graph candidates.
- Automatically deduplicates records present in both MongoDB Atlas and Neo4j Aura.
- Transparently degrades to MongoDB category and rating ranking if Neo4j is offline.

---

## Analytics Dashboard (Phase 8)

Located at `pages/5_Analytics_Dashboard.py` with backing logic in `services/analytics_service.py`, TasteTrail provides a rich analytical dashboard combining MongoDB aggregations and Neo4j graph topology.

### 1. Live KPI Summary
- **MongoDB Atlas Collections:** Total Restaurants, Imported Customer Reviews, Users, Average Venue Stars, Unique Cuisines, Municipalities.
- **Neo4j Aura Graph Database:** Total Graph Nodes, Total Directed Relationships, and detailed breakdowns (Restaurants, Users, Categories, Cities, and REVIEWED/BELONGS_TO/LOCATED_IN edges).
- **Integrity Guarantee:** Document counts and graph metrics are clearly distinguished; missing databases fall back gracefully without fabricated numbers.

### 2. Multi-Criteria Interactive Filtering
- Filters by **City**, **Cuisine / Category**, and **Minimum Stars**.
- Filter scope indicators clearly show whether charts reflect filtered parameters or global population metrics.
- A **🔄 Refresh Data** button resets cached aggregations on demand.

### 3. Visualizations (Plotly with TasteTrail Theme)
- **Restaurant Rating Distribution:** Categorical breakdown of star ratings (1.0★–5.0★).
- **Top Cuisines by Restaurant Count:** Horizontal bar chart showing venue volume and average rating hovers.
- **Geographic Distribution:** Municipal restaurant cluster counts and star ratings.
- **Customer Review Breakdown:** 1★–5★ sentiment-colored bar chart across imported review samples.
- **Review Volume & Rating Timeline:** Dual-trace timeline displaying review count and rating progression over years.

### 4. CSV Export Capabilities
Provides one-click UTF-8 CSV downloads for tabular data:
- `tastetrail_top_rated_restaurants.csv`
- `tastetrail_most_reviewed_restaurants.csv`
- `tastetrail_cuisine_summary.csv`
- `tastetrail_city_summary.csv`

---

## Testing

```powershell
# Run the entire test suite (138+ automated tests):
.\venv\Scripts\pytest -v

# Run Phase 1 structure & configuration tests:
.\venv\Scripts\pytest tests/test_phase1_setup.py -v

# Run Phase 2 data cleaning & validation tests:
.\venv\Scripts\pytest tests/test_data_validation.py -v

# Run Phase 3 MongoDB query & integration tests:
.\venv\Scripts\pytest tests/test_mongodb_integration.py -v

# Run Phase 4 Neo4j query & graph integration tests:
.\venv\Scripts\pytest tests/test_neo4j_integration.py -v

# Run Phase 5 Homepage & Explore UI tests:
.\venv\Scripts\pytest tests/test_phase5_ui.py -v

# Run Phase 6 Restaurant Details & Reviews tests:
.\venv\Scripts\pytest tests/test_phase6_details.py -v

# Run Phase 7 Recommendation Service unit & integration tests:
.\venv\Scripts\pytest tests/test_recommendation_service.py tests/test_phase7_recommendations.py -v

# Run Phase 8 Analytics Dashboard & aggregation tests:
.\venv\Scripts\pytest tests/test_phase8_analytics.py -v

# Run Phase 9 End-to-End integration & deployment readiness tests:
.\venv\Scripts\pytest tests/test_phase9_e2e.py -v
```

---

## Deployment

### Streamlit Community Cloud

1. Push the repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo.
3. Set environment variables in the Streamlit Secrets panel (TOML format):
   ```toml
   MONGODB_URI = "mongodb+srv://..."
   MONGODB_DATABASE = "restaurant_recommendation"
   NEO4J_URI = "neo4j+s://..."
   NEO4J_USERNAME = "neo4j"
   NEO4J_PASSWORD = "..."
   ```
4. Deploy – Streamlit installs `requirements.txt` automatically.

---

## Screenshots

*Screenshots will be added after all phases are complete.*

---

## Limitations

- Uses a sample of the Yelp dataset, not the full corpus.
- Recommendations are content-based and graph-based, not machine-learning personalised.
- No user authentication in the current version.
- For educational purposes only; not affiliated with Yelp Inc.

---

## Acknowledgements

- [Yelp Open Dataset](https://www.yelp.com/dataset)
- [MongoDB](https://www.mongodb.com)
- [Neo4j](https://neo4j.com)
- [Streamlit](https://streamlit.io)
