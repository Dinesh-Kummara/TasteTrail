"""
services/analytics_service.py
─────────────────────────────
Analytics engine and visualization service for TasteTrail.

Features:
1. Plotly chart builders adhering to TasteTrail design theme:
   - Restaurant star rating distribution
   - Category distribution (counts + average ratings)
   - City-wise restaurant distribution
   - Customer review star breakdown
   - Review volume and rating time trends
2. KPI summary aggregation distinguishing MongoDB document counts from Neo4j graph counts.
3. Clean CSV export DataFrame builders for rankings, categories, and cities.
4. Safe error handling, zero-data resilience, and missing field fallbacks.
"""

import logging
from typing import Any
import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger("tastetrail.analytics_service")

# TasteTrail Theme Color Constants
NAVY = "#0D1B2A"
ORANGE = "#F4681E"
ORANGE_LIGHT = "#FED7AA"
BLUE_ACCENT = "#2563EB"
SLATE_MUTED = "#64748B"
GRID_COLOR = "#F1F5F9"


def apply_tastetrail_chart_theme(
    fig: go.Figure,
    title: str,
    height: int = 380,
    show_legend: bool = False,
) -> go.Figure:
    """Apply consistent TasteTrail styling and typography to Plotly figures."""
    fig.update_layout(
        title={
            "text": f"<b>{title}</b>",
            "font": {"size": 15, "color": NAVY, "family": "Inter, sans-serif"},
            "x": 0.02,
            "xanchor": "left",
        },
        height=height,
        margin={"l": 40, "r": 30, "t": 50, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": "#374151", "size": 12},
        showlegend=show_legend,
        hoverlabel={"bgcolor": NAVY, "font_color": "#FFFFFF", "font_size": 12},
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=GRID_COLOR,
        linecolor="#E2E8F0",
        tickfont={"size": 11, "color": SLATE_MUTED},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=GRID_COLOR,
        linecolor="#E2E8F0",
        tickfont={"size": 11, "color": SLATE_MUTED},
    )
    return fig


# ── Chart Builders ─────────────────────────────────────────────────────────────

def create_rating_distribution_chart(
    data: list[dict],
    title: str = "Restaurant Rating Distribution",
) -> go.Figure:
    """
    Generate bar chart of restaurant count grouped by star ratings.
    data format: [{'stars': 4.5, 'count': 42}, ...]
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No rating data available for selected filters",
            showarrow=False,
            font={"size": 13, "color": SLATE_MUTED},
        )
        return apply_tastetrail_chart_theme(fig, title)

    df = pd.DataFrame(data).dropna(subset=["stars", "count"])
    df = df.sort_values(by="stars")

    fig = go.Figure(
        data=[
            go.Bar(
                x=[f"{s:.1f}★" for s in df["stars"]],
                y=df["count"],
                marker={"color": ORANGE, "line": {"color": "#C2410C", "width": 1.2}},
                hovertemplate="Rating: <b>%{x}</b><br>Restaurants: <b>%{y:,}</b><extra></extra>",
            )
        ]
    )
    fig.update_layout(xaxis_title="Star Rating", yaxis_title="Restaurant Count")
    return apply_tastetrail_chart_theme(fig, title)


def create_category_distribution_chart(
    data: list[dict],
    title: str = "Top Cuisines by Venue Count",
) -> go.Figure:
    """
    Generate horizontal bar chart showing top restaurant categories.
    data format: [{'category': 'Italian', 'count': 18, 'avg_rating': 4.3}, ...]
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No category data available for selected filters",
            showarrow=False,
            font={"size": 13, "color": SLATE_MUTED},
        )
        return apply_tastetrail_chart_theme(fig, title)

    df = pd.DataFrame(data).dropna(subset=["category", "count"])
    # Sort ascending for horizontal bar chart
    df = df.sort_values(by="count", ascending=True)

    hover_texts = [
        f"Cuisine: <b>{row['category']}</b><br>Venues: <b>{row['count']:,}</b><br>Avg Rating: <b>{row.get('avg_rating', 0.0):.2f}★</b>"
        for _, row in df.iterrows()
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["count"],
                y=df["category"],
                orientation="h",
                marker={"color": BLUE_ACCENT},
                hovertext=hover_texts,
                hoverinfo="text",
            )
        ]
    )
    fig.update_layout(xaxis_title="Restaurant Count", yaxis_title="")
    return apply_tastetrail_chart_theme(fig, title, height=max(360, len(df) * 28))


def create_city_distribution_chart(
    data: list[dict],
    title: str = "Geographic Distribution (Top Cities)",
) -> go.Figure:
    """
    Generate bar chart for restaurant counts and average ratings across cities.
    data format: [{'city': 'Philadelphia', 'count': 45, 'avg_rating': 4.1}, ...]
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No city distribution data available",
            showarrow=False,
            font={"size": 13, "color": SLATE_MUTED},
        )
        return apply_tastetrail_chart_theme(fig, title)

    df = pd.DataFrame(data).dropna(subset=["city", "count"])
    df = df.sort_values(by="count", ascending=False)

    hover_texts = [
        f"City: <b>{row['city']}</b><br>Restaurants: <b>{row['count']:,}</b><br>Avg Rating: <b>{row.get('avg_rating', 0.0):.2f}★</b>"
        for _, row in df.iterrows()
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["city"],
                y=df["count"],
                marker={"color": NAVY},
                hovertext=hover_texts,
                hoverinfo="text",
            )
        ]
    )
    fig.update_layout(xaxis_title="City", yaxis_title="Restaurant Count")
    return apply_tastetrail_chart_theme(fig, title)


def create_review_star_distribution_chart(
    data: list[dict],
    title: str = "Imported Review Star Distribution",
) -> go.Figure:
    """
    Generate bar chart of individual customer review ratings.
    data format: [{'stars': 5.0, 'count': 180}, ...]
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No review star distribution data available",
            showarrow=False,
            font={"size": 13, "color": SLATE_MUTED},
        )
        return apply_tastetrail_chart_theme(fig, title)

    df = pd.DataFrame(data).dropna(subset=["stars", "count"])
    df = df.sort_values(by="stars")

    # Color palette tailored by sentiment
    star_colors = {
        1.0: "#EF4444",
        2.0: "#F97316",
        3.0: "#FBBF24",
        4.0: "#84CC16",
        5.0: "#10B981",
    }
    colors = [star_colors.get(round(float(s)), ORANGE) for s in df["stars"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=[f"{s:.0f}★" for s in df["stars"]],
                y=df["count"],
                marker={"color": colors},
                hovertemplate="Rating: <b>%{x}</b><br>Reviews: <b>%{y:,}</b><extra></extra>",
            )
        ]
    )
    fig.update_layout(xaxis_title="Stars", yaxis_title="Review Count")
    return apply_tastetrail_chart_theme(fig, title)


def create_review_timeline_chart(
    data: list[dict],
    title: str = "Review Volume Trends by Year",
) -> go.Figure:
    """
    Generate line chart of review submission volume and average star rating over years.
    data format: [{'year': '2019', 'count': 85, 'avg_rating': 4.12}, ...]
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No review timeline data available",
            showarrow=False,
            font={"size": 13, "color": SLATE_MUTED},
        )
        return apply_tastetrail_chart_theme(fig, title)

    df = pd.DataFrame(data).dropna(subset=["year", "count"])
    df = df.sort_values(by="year")

    fig = go.Figure()
    # Review count bars
    fig.add_trace(
        go.Bar(
            x=df["year"],
            y=df["count"],
            name="Reviews",
            marker={"color": ORANGE_LIGHT, "line": {"color": ORANGE, "width": 1.5}},
            hovertemplate="Year: <b>%{x}</b><br>Reviews: <b>%{y:,}</b><extra></extra>",
        )
    )
    # Average rating line overlay
    if "avg_rating" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=df["avg_rating"],
                name="Avg Rating",
                yaxis="y2",
                mode="lines+markers",
                line={"color": NAVY, "width": 2.5},
                marker={"size": 6, "color": NAVY},
                hovertemplate="Year: <b>%{x}</b><br>Avg Rating: <b>%{y:.2f}★</b><extra></extra>",
            )
        )

    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Review Count",
        yaxis2={
            "title": "Avg Rating (Stars)",
            "overlaying": "y",
            "side": "right",
            "range": [1.0, 5.0],
            "showgrid": False,
        },
    )
    return apply_tastetrail_chart_theme(fig, title, show_legend=True)


# ── CSV Export Builders ────────────────────────────────────────────────────────

def prepare_rankings_export_df(restaurants: list[dict]) -> pd.DataFrame:
    """Prepare clean, formatted DataFrame for restaurant rankings export."""
    if not restaurants:
        return pd.DataFrame(
            columns=["Rank", "Name", "City", "Stars", "Review Count", "Categories", "Business ID"]
        )

    rows = []
    for idx, r in enumerate(restaurants, start=1):
        raw_cats = r.get("categories") or []
        cats_str = ", ".join(raw_cats) if isinstance(raw_cats, list) else str(raw_cats)
        rows.append({
            "Rank": idx,
            "Name": r.get("name", "Unknown"),
            "City": r.get("city", ""),
            "Stars": round(float(r.get("stars", 0.0)), 1),
            "Review Count": int(r.get("review_count", 0)),
            "Categories": cats_str,
            "Business ID": r.get("business_id", ""),
        })
    return pd.DataFrame(rows)


def prepare_category_export_df(categories: list[dict]) -> pd.DataFrame:
    """Prepare clean DataFrame for category summary export."""
    if not categories:
        return pd.DataFrame(columns=["Category", "Restaurant Count", "Average Rating"])

    rows = [
        {
            "Category": c.get("category", ""),
            "Restaurant Count": int(c.get("count", 0)),
            "Average Rating": round(float(c.get("avg_rating", 0.0)), 2),
        }
        for c in categories
    ]
    return pd.DataFrame(rows)


def prepare_city_export_df(cities: list[dict]) -> pd.DataFrame:
    """Prepare clean DataFrame for city summary export."""
    if not cities:
        return pd.DataFrame(columns=["City", "Restaurant Count", "Average Rating"])

    rows = [
        {
            "City": c.get("city", ""),
            "Restaurant Count": int(c.get("count", 0)),
            "Average Rating": round(float(c.get("avg_rating", 0.0)), 2),
        }
        for c in cities
    ]
    return pd.DataFrame(rows)


# ── KPI Aggregator ─────────────────────────────────────────────────────────────

def get_kpi_summary(mongo_metrics: dict, graph_metrics: dict | None = None) -> dict:
    """
    Structure KPI metrics payload distinguishing MongoDB document counts from Neo4j graph counts.
    Never fabricates missing figures.
    """
    mm = mongo_metrics or {}
    gm = graph_metrics or {}

    total_graph_nodes = sum([
        gm.get("restaurant_count", 0),
        gm.get("user_count", 0),
        gm.get("category_count", 0),
        gm.get("city_count", 0),
    ])
    total_graph_rels = sum([
        gm.get("reviewed_count", 0),
        gm.get("belongs_to_count", 0),
        gm.get("located_in_count", 0),
    ])

    return {
        "mongodb": {
            "total_restaurants": int(mm.get("total_restaurants", 0)),
            "total_reviews": int(mm.get("total_reviews", 0)),
            "total_users": int(mm.get("total_users", 0)),
            "average_rating": float(mm.get("average_rating", 0.0)),
            "total_categories": int(mm.get("total_categories", 0)),
            "total_cities": int(mm.get("total_cities", 0)),
        },
        "neo4j": {
            "is_available": bool(graph_metrics and total_graph_nodes > 0),
            "total_nodes": total_graph_nodes,
            "total_relationships": total_graph_rels,
            "node_details": {
                "Restaurant": gm.get("restaurant_count", 0),
                "User": gm.get("user_count", 0),
                "Category": gm.get("category_count", 0),
                "City": gm.get("city_count", 0),
            },
            "relationship_details": {
                "REVIEWED": gm.get("reviewed_count", 0),
                "BELONGS_TO": gm.get("belongs_to_count", 0),
                "LOCATED_IN": gm.get("located_in_count", 0),
            },
        },
    }
