import os
from datetime import datetime

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

st.set_page_config(
    page_title="VictoryAI | Job Intelligence",
    page_icon="🚀",
    layout="wide",
)

DATABASE_URL = os.getenv("DATABASE_URL")


st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .main-title {
            font-size: 42px;
            font-weight: 800;
            letter-spacing: -1.5px;
            margin-bottom: 0px;
        }

        .subtitle {
            color: #6b7280;
            font-size: 16px;
            margin-bottom: 28px;
        }

        .metric-card {
            background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
            padding: 22px;
            border-radius: 18px;
            border: 1px solid #374151;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
        }

        .metric-label {
            color: #9ca3af;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 8px;
        }

        .metric-value {
            color: white;
            font-size: 34px;
            font-weight: 800;
        }

        .job-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 22px;
            margin-bottom: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }

        .job-title {
            font-size: 21px;
            font-weight: 750;
            color: #111827;
            margin-bottom: 6px;
        }

        .job-meta {
            color: #4b5563;
            font-size: 14px;
            margin-bottom: 14px;
        }

        .pill {
            display: inline-block;
            padding: 5px 11px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            margin-right: 6px;
            margin-bottom: 6px;
        }

        .pill-green {
            background: #dcfce7;
            color: #166534;
        }

        .pill-blue {
            background: #dbeafe;
            color: #1d4ed8;
        }

        .pill-purple {
            background: #ede9fe;
            color: #6d28d9;
        }

        .pill-gray {
            background: #f3f4f6;
            color: #374151;
        }

        .section-header {
            font-size: 24px;
            font-weight: 800;
            margin-top: 22px;
            margin-bottom: 12px;
            color: #111827;
        }

        .small-muted {
            color: #6b7280;
            font-size: 13px;
        }

        div[data-testid="stSidebar"] {
            background-color: #f9fafb;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def load_jobs():
    if not DATABASE_URL:
        return pd.DataFrame()

    conn = psycopg2.connect(DATABASE_URL)

    query = """
        SELECT
            title,
            company,
            location,
            country,
            source,
            url,
            posted_date,
            relevance_bucket,
            embedding_score,
            match_score,
            recommendation,
            description,
            first_seen_at,
            last_seen_at,
            is_new_24h
        FROM jobs
        ORDER BY embedding_score DESC NULLS LAST, first_seen_at DESC NULLS LAST
        LIMIT 2000;
    """

    df = pd.read_sql(query, conn)
    conn.close()
    return df


def safe_count(series, value):
    if series is None:
        return 0
    return int((series == value).sum())


def format_date(value):
    if not value:
        return ""
    try:
        return pd.to_datetime(value).strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(value)


def score_pill(score):
    try:
        score = float(score)
    except Exception:
        score = 0

    if score >= 60:
        return "pill-green"
    if score >= 35:
        return "pill-blue"
    return "pill-gray"


st.markdown('<div class="main-title">🚀 VictoryAI Job Intelligence</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Cloud-deployed AI system for multi-source job discovery, semantic matching, and career market intelligence.</div>',
    unsafe_allow_html=True,
)

df = load_jobs()

if df.empty:
    st.warning("No jobs found in PostgreSQL yet. Run the worker pipeline once.")
    st.stop()

for col in [
    "title", "company", "location", "country", "source", "url",
    "posted_date", "relevance_bucket", "embedding_score", "match_score",
    "recommendation", "description", "first_seen_at", "last_seen_at", "is_new_24h"
]:
    if col not in df.columns:
        df[col] = ""

df["embedding_score"] = pd.to_numeric(df["embedding_score"], errors="coerce").fillna(0)
df["match_score"] = pd.to_numeric(df["match_score"], errors="coerce").fillna(0)
df["is_new_24h"] = df["is_new_24h"].fillna(False).astype(bool)

recommended_count = df["recommendation"].isin(["Strong Match", "Good Match", "Possible Match"]).sum()
avg_score = round(df["embedding_score"].mean(), 2)
new_24h = int(df["is_new_24h"].sum())
sources = int(df["source"].nunique())

m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Jobs Indexed</div>
            <div class="metric-value">{len(df)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Recommended</div>
            <div class="metric-value">{recommended_count}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">New 24h</div>
            <div class="metric-value">{new_24h}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Avg AI Score</div>
            <div class="metric-value">{avg_score}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m5:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Sources</div>
            <div class="metric-value">{sources}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-header">Search & Filters</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Control Panel")

    recommendations = sorted([x for x in df["recommendation"].dropna().unique() if x])
    relevance_buckets = sorted([x for x in df["relevance_bucket"].dropna().unique() if x])
    sources_list = sorted([x for x in df["source"].dropna().unique() if x])

    selected_recommendations = st.multiselect(
        "Recommendation",
        options=recommendations,
        default=recommendations,
    )

    selected_relevance = st.multiselect(
        "Relevance",
        options=relevance_buckets,
        default=relevance_buckets,
    )

    selected_sources = st.multiselect(
        "Source",
        options=sources_list,
        default=sources_list,
    )

    min_score = st.slider(
        "Minimum AI Score",
        min_value=0,
        max_value=100,
        value=0,
    )

    only_new = st.checkbox("Only new in last 24h", value=False)

    st.divider()

    title_search = st.text_input("Title contains")
    company_search = st.text_input("Company contains")
    location_search = st.text_input("Location contains")

filtered = df.copy()

if selected_recommendations:
    filtered = filtered[filtered["recommendation"].isin(selected_recommendations)]

if selected_relevance:
    filtered = filtered[filtered["relevance_bucket"].isin(selected_relevance)]

if selected_sources:
    filtered = filtered[filtered["source"].isin(selected_sources)]

filtered = filtered[filtered["embedding_score"] >= min_score]

if only_new:
    filtered = filtered[filtered["is_new_24h"] == True]

if title_search:
    filtered = filtered[filtered["title"].astype(str).str.contains(title_search, case=False, na=False)]

if company_search:
    filtered = filtered[filtered["company"].astype(str).str.contains(company_search, case=False, na=False)]

if location_search:
    filtered = filtered[filtered["location"].astype(str).str.contains(location_search, case=False, na=False)]

tab1, tab2, tab3 = st.tabs(["🏆 Recommendations", "📊 Analytics", "🧾 Data Table"])

with tab1:
    st.markdown(
        f'<div class="section-header">Top Matches ({len(filtered)})</div>',
        unsafe_allow_html=True,
    )

    for _, row in filtered.head(80).iterrows():
        score = row.get("embedding_score", 0)
        pill_class = score_pill(score)

        st.markdown(
            f"""
            <div class="job-card">
                <div class="job-title">{row.get("title", "")}</div>
                <div class="job-meta">
                    <b>{row.get("company", "")}</b> · {row.get("location", "")} · {row.get("source", "")}
                </div>
                <span class="pill {pill_class}">AI Score: {score}</span>
                <span class="pill pill-purple">{row.get("recommendation", "")}</span>
                <span class="pill pill-blue">{row.get("relevance_bucket", "")}</span>
                <span class="pill pill-gray">First seen: {format_date(row.get("first_seen_at", ""))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns([1, 5])

        with col_a:
            url = row.get("url", "")
            if isinstance(url, str) and url:
                st.link_button("Open Role", url, use_container_width=True)

        with col_b:
            with st.expander("View description"):
                st.write(row.get("description", ""))

with tab2:
    a1, a2 = st.columns(2)

    with a1:
        st.markdown('<div class="section-header">Jobs by Source</div>', unsafe_allow_html=True)
        source_counts = filtered["source"].value_counts().reset_index()
        source_counts.columns = ["source", "count"]
        st.bar_chart(source_counts.set_index("source"))

    with a2:
        st.markdown('<div class="section-header">Recommendation Mix</div>', unsafe_allow_html=True)
        rec_counts = filtered["recommendation"].value_counts().reset_index()
        rec_counts.columns = ["recommendation", "count"]
        st.bar_chart(rec_counts.set_index("recommendation"))

    st.markdown('<div class="section-header">Top Companies</div>', unsafe_allow_html=True)
    company_counts = filtered["company"].value_counts().head(20).reset_index()
    company_counts.columns = ["company", "count"]
    st.dataframe(company_counts, use_container_width=True, hide_index=True)

with tab3:
    st.markdown('<div class="section-header">Indexed Job Records</div>', unsafe_allow_html=True)

    display_cols = [
        "title",
        "company",
        "location",
        "source",
        "relevance_bucket",
        "embedding_score",
        "recommendation",
        "first_seen_at",
        "url",
    ]

    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
    )

st.caption(f"Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")