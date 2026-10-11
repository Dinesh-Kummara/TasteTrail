"""
components/rating_display.py
─────────────────────────────
Reusable rating star renderers.
"""

import streamlit as st


def star_html(rating: float, max_stars: int = 5) -> str:
    """Return an HTML string of filled/half/empty Unicode stars."""
    stars = ""
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 else 0
    empty = max_stars - full - half

    stars += "★" * full
    stars += "½" * half
    stars += "☆" * empty
    return f'<span style="color:#F4681E; font-size:1rem;">{stars}</span>'


def render_rating_badge(rating: float, review_count: int | None = None) -> None:
    """Render an inline rating badge using st.markdown."""
    stars = star_html(rating)
    count_html = (
        f'<span style="color:#6B7280; font-size:0.82rem;"> ({review_count:,} reviews)</span>'
        if review_count is not None
        else ""
    )
    st.markdown(
        f'<div style="margin:0.3rem 0;">{stars} '
        f'<strong style="color:#F4681E;">{rating:.1f}</strong>'
        f"{count_html}</div>",
        unsafe_allow_html=True,
    )
