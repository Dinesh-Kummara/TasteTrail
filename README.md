# 🍽️ TasteTrail — Restaurant Review and Recommendation System

> **Discover places worth tasting.**  
> A restaurant discovery, recommendation, and analytics application built using the Yelp Open Dataset, MongoDB Atlas, Neo4j, Python, and Streamlit.

**🌐 Live Application:** https://tastetrail-dinesh.streamlit.app/

---

## 📋 Table of Contents

1. Project Overview
2. Features
3. Technology Stack
4. System Architecture
5. Dataset Description
6. Recommendation Methodology
7. Analytics Dashboard
8. Project Structure
9. Installation and Setup
10. Environment Configuration
11. Running the Application
12. Testing
13. Deployment
14. Limitations and Future Improvements
15. Acknowledgements

---

## 📌 Project Overview

TasteTrail is a web-based restaurant discovery and recommendation system developed as an academic database engineering microproject.

The application helps users explore restaurants, compare ratings, discover restaurants by location and category, receive restaurant recommendations, and analyze restaurant reviews through an interactive dashboard.

The project combines a document database with a graph database to manage restaurant information and relationships efficiently.

### Objectives

- Develop an interactive restaurant discovery application.
- Store restaurant, user, and review data in MongoDB.
- Model user–restaurant–category relationships using Neo4j.
- Recommend similar restaurants using category similarity and rating-based scoring.
- Visualize restaurant ratings, categories, locations, and review statistics.
- Deploy the application using Streamlit Community Cloud.

---

## ✨ Features

### 1. Restaurant Search

- Search for restaurants by name.
- Browse restaurant details and available ratings.
- Explore restaurant categories and locations.
- Access restaurant information through an interactive interface.

### 2. Rating Distribution

- Visualize the distribution of restaurant ratings.
- Compare restaurant rating patterns.
- Understand the rating distribution through interactive charts.

### 3. Category-wise Analysis

- Analyze restaurants by category or cuisine.
- Compare categories based on restaurant counts.
- Explore available category-related rating information.

### 4. Location-based Restaurant Discovery

- Discover restaurants using available location information.
- Filter restaurant results by supported location criteria.
- Explore restaurant distribution across available cities.

### 5. Most Reviewed Restaurants

- Rank restaurants using their available review counts.
- Identify restaurants with higher review activity.
- Compare review volume across restaurant listings.

### 6. Recommended Restaurants

- Select a restaurant to discover similar venues.
- Use category similarity to identify related restaurants.
- Incorporate rating-based scoring into recommendations.
- Apply supported filters such as location, category, and minimum rating.

### 7. User Review Analysis

- Explore available user review information.
- Analyze review counts and rating-related statistics.
- Examine user–restaurant relationships where graph data is available.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and data processing |
| Streamlit | Interactive web application |
| MongoDB Atlas | Document-oriented data storage |
| Neo4j | Graph database and relationship modelling |
| PyMongo | MongoDB connectivity |
| Neo4j Python Driver | Neo4j connectivity and Cypher queries |
| Pandas | Data processing and manipulation |
| Plotly | Interactive charts and visualizations |
| python-dotenv | Environment variable configuration |

Package versions are maintained in `requirements.txt`.

---

## 🏗️ System Architecture

```text
             Yelp Open Dataset
                     |
                     v
          Data Preprocessing
          and Data Cleaning
                     |
             +-------+-------+
             |               |
             v               v
       MongoDB Atlas        Neo4j
       Document Store     Graph Database
             |               |
             +-------+-------+
                     |
                     v
       Recommendation and Analytics
                 Services
                     |
                     v
             Streamlit UI
                     |
                     v
         Restaurant Discovery,
         Recommendations, and
         Analytics Dashboard
```

### Architecture Components

**MongoDB Atlas**

Stores and retrieves document-oriented restaurant, user, and review information.

**Neo4j**

Represents relationships between users, restaurants, and categories through graph nodes and relationships.

**Recommendation Service**

Ranks restaurant candidates using the implemented category-similarity and rating-based scoring logic.

**Analytics Service**

Processes available data and generates analytical summaries and interactive visualizations.

**Streamlit Application**

Provides the user interface for searching, exploring, recommending, and analyzing restaurants.

---

## 📊 Dataset Description

TasteTrail uses the **Yelp Open Dataset**.

Dataset source: https://www.yelp.com/dataset

The core data entities are:

| Dataset | Important Fields | Purpose |
|---|---|---|
| Business | `business_id`, `name`, `city`, `state`, `stars`, `review_count`, `categories` | Restaurant information |
| Review | `review_id`, `user_id`, `business_id`, `stars`, `date`, `text` | Customer reviews and ratings |
| User | `user_id`, `name`, `review_count`, `average_stars` | User information and review activity |

### Data Processing

The data preparation workflow includes:

1. Loading the required Yelp dataset files.
2. Selecting business, review, and user information.
3. Filtering restaurant records.
4. Cleaning and normalizing available fields.
5. Preparing records for database ingestion.
6. Storing document data in MongoDB.
7. Modelling relationships in Neo4j.

Dataset counts may vary according to the data loaded into the configured databases.

---

## 🧠 Recommendation Methodology

TasteTrail uses a recommendation and ranking approach based on category similarity and rating quality. It is not a trained machine-learning model.

### 1. Category Similarity — Jaccard Index

The Jaccard index measures the overlap between two restaurants' categories.

\[
J(A,B)=\frac{|A\cap B|}{|A\cup B|}
\]

Where:

- \(A\) represents the categories of the reference restaurant.
- \(B\) represents the categories of a candidate restaurant.
- A higher score indicates greater category overlap.

### 2. Bayesian Rating Adjustment

A Bayesian-style rating adjustment reduces the influence of ratings supported by a small number of reviews.

\[
BR=\frac{v}{v+m}R+\frac{m}{v+m}C
\]

Where:

- \(R\) is the restaurant's average rating.
- \(v\) is its review count.
- \(C\) is the average rating of the relevant candidate set.
- \(m\) is the review-confidence parameter.

### 3. Composite Recommendation Score

The service combines category similarity and adjusted rating into a weighted score.

\[
Score=100\left(w_cJ(A,B)+w_r\frac{BR}{5}\right)
\]

The documented default weights are:

- Category similarity: 60%
- Rating quality: 40%

The recommendation results depend on available records, the selected restaurant, and the applied filters.

---

## 📈 Analytics Dashboard

The analytics dashboard provides interactive visualizations and summaries based on available database information.

### Dashboard Capabilities

- Restaurant rating distribution.
- Category-wise restaurant analysis.
- Geographic distribution of restaurants.
- Review-related summaries.
- Restaurant and user statistics where available.
- Graph node and relationship metrics when Neo4j is reachable.
- Supported filters for location, category, and minimum rating.
- CSV exports for supported summary tables.

The values displayed depend on the currently configured databases and available data.

---

## 📁 Project Structure

The following is a high-level representation of the project structure. Exact filenames may differ from the current repository.

```text
tastetrail/
│
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── .streamlit/
│   └── config.toml
│
├── config/
│   └── settings.py
│
├── pages/
│
├── components/
│
├── database/
│
├── services/
│
├── data_pipeline/
│
├── scripts/
│
└── tests/
```

### Main Components

- `app.py` — Streamlit application entry point.
- `pages/` — Application pages, where applicable.
- `components/` — Reusable interface components.
- `database/` — Database connections and query logic.
- `services/` — Recommendation and analytics logic.
- `data_pipeline/` — Dataset preparation and import utilities, if included.
- `scripts/` — Database verification and utility scripts.
- `tests/` — Automated tests.

---

## 💻 Installation and Setup

### Prerequisites

- Python version supported by `requirements.txt`.
- Git.
- A configured MongoDB Atlas database.
- A configured Neo4j instance.
- Network access to the configured database services.

### Step 1: Clone the Repository

Replace the placeholder with your actual GitHub repository URL.

```bash
git clone <your-github-repository-url>
cd <repository-folder>
```

### Step 2: Create a Virtual Environment

**Windows PowerShell**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Copy the example environment file.

**Windows**

```powershell
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
cp .env.example .env
```

Configure the required database settings in `.env` using the variable names expected by the application.

Do not commit real credentials to GitHub.

---

## 🔐 Environment Configuration

The application uses environment variables to configure database connections.

Example placeholders:

```ini
MONGODB_URI=<your-mongodb-atlas-connection-string>
MONGODB_DATABASE=<your-database-name>

NEO4J_URI=<your-neo4j-connection-uri>
NEO4J_USERNAME=<your-neo4j-username>
NEO4J_PASSWORD=<your-neo4j-password>
NEO4J_DATABASE=<your-neo4j-database>
```

Use the exact variable names expected by your current `config/settings.py` and database connection modules.

### Security Best Practices

- Keep `.env` out of version control.
- Commit only placeholder values in `.env.example`.
- Configure production secrets through the deployment platform.
- Rotate any credentials that have been exposed publicly.
- Never display database passwords or complete connection strings in application logs.

---

## ▶️ Running the Application

From the project root, run:

**Windows PowerShell**

```powershell
.\venv\Scripts\python.exe -m streamlit run app.py
```

**macOS / Linux**

```bash
streamlit run app.py
```

The application will normally be available at:

http://localhost:8501

Ensure the configured database services are reachable before using features that require database access.

---

## 🧪 Testing

Run the available automated tests from the project root.

```powershell
.\venv\Scripts\python.exe -m pytest -v
```

To run a specific test file:

```powershell
.\venv\Scripts\python.exe -m pytest tests/<test-file>.py -v
```

Some integration tests require valid database credentials and reachable MongoDB and Neo4j instances.

Only report tests as passed when they have actually been executed successfully.

---

## 🚀 Deployment

TasteTrail is deployed using Streamlit Community Cloud.

### Live Application

**https://tastetrail-dinesh.streamlit.app/**

### Deployment Steps

1. Push the project to GitHub.
2. Open https://share.streamlit.io/.
3. Connect the GitHub repository.
4. Select `app.py` as the application entry point.
5. Configure the database credentials in the application's secrets settings.
6. Deploy the application.
7. Verify that the application pages and database connections work correctly.

The deployed environment must have valid credentials and network access to the configured database services.

Never store database credentials directly in source code.

---

## ⚠️ Limitations and Future Improvements

### Current Limitations

- Recommendation quality depends on the coverage and quality of available restaurant and review data.
- Recommendations use category similarity and rating-based ranking rather than a trained personalized machine-learning model.
- Recommendations may be limited when a restaurant has incomplete information.
- Dashboard metrics depend on the configured databases and available records.
- User authentication and personal profiles are not included unless implemented separately.

### Future Improvements

- Evaluate recommendation quality using ranking metrics and test data.
- Introduce optional user profiles and preference-based personalization.
- Improve caching and database query performance.
- Expand automated testing and deployment monitoring.
- Enhance graph-based recommendations and relationship analysis.
- Improve usability and accessibility across devices.

---

## 🙏 Acknowledgements

- [Yelp Open Dataset](https://www.yelp.com/dataset)
- [MongoDB Atlas](https://www.mongodb.com/atlas)
- [Neo4j](https://neo4j.com/)
- [Streamlit](https://streamlit.io/)
- [Plotly](https://plotly.com/)

---

## 👨‍💻 Author

**Dinesh Kummara**  
B.Tech — Computer Science and Engineering  
Alliance School of Advanced Computing, Alliance University

**Project:** TasteTrail — Restaurant Review and Recommendation System using MongoDB and Neo4j

**Live Application:** https://tastetrail-dinesh.streamlit.app/

---

*Developed as an academic database engineering microproject.*
