import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="VictoryAI Dashboard",
    page_icon="🚀",
    layout="wide"
)

DATA_PATH = "data/applications.csv"

st.title("🚀 VictoryAI Job Dashboard")
st.caption("Personal Jobright-style job finder for AI, analytics, ML, and data roles.")

try:
    df = pd.read_csv(DATA_PATH)
except Exception:
    st.error("No applications.csv found. Run: python -m orchestrator.workflow")
    st.stop()

if df.empty:
    st.warning("No jobs found yet.")
    st.stop()

for col in [
    "title", "company", "location", "relevance_bucket",
    "date_status", "source", "url", "posted_date"
]:
    if col not in df.columns:
        df[col] = ""

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Relevant Jobs Found", len(df))

with col2:
    st.metric("Strong Relevant", (df["relevance_bucket"] == "Strong Relevant").sum())

with col3:
    st.metric("Possible Relevant", (df["relevance_bucket"] == "Possible Relevant").sum())

st.divider()

bucket_filter = st.multiselect(
    "Filter by relevance",
    options=sorted(df["relevance_bucket"].dropna().unique()),
    default=list(sorted(df["relevance_bucket"].dropna().unique()))
)

location_search = st.text_input("Search location", "")
company_search = st.text_input("Search company", "")
title_search = st.text_input("Search title", "")

filtered = df.copy()

if bucket_filter:
    filtered = filtered[filtered["relevance_bucket"].isin(bucket_filter)]

if location_search:
    filtered = filtered[
        filtered["location"].str.contains(location_search, case=False, na=False)
    ]

if company_search:
    filtered = filtered[
        filtered["company"].str.contains(company_search, case=False, na=False)
    ]

if title_search:
    filtered = filtered[
        filtered["title"].str.contains(title_search, case=False, na=False)
    ]

st.subheader(f"Jobs Showing: {len(filtered)}")

display_cols = [
    "title",
    "company",
    "location",
    "relevance_bucket",
    "date_status",
    "posted_date",
    "source",
    "url",
]

st.dataframe(
    filtered[display_cols],
    use_container_width=True,
    hide_index=True
)

st.divider()

st.subheader("Job Cards")

for _, row in filtered.iterrows():
    with st.container(border=True):
        st.markdown(f"### {row.get('title', '')}")
        st.write(f"**Company:** {row.get('company', '')}")
        st.write(f"**Location:** {row.get('location', '')}")
        st.write(f"**Relevance:** {row.get('relevance_bucket', '')}")
        st.write(f"**Date:** {row.get('posted_date', '') or row.get('date_status', '')}")
        st.write(f"**Source:** {row.get('source', '')}")

        url = row.get("url", "")
        if isinstance(url, str) and url:
            st.link_button("Apply / Open Career Page", url)

        with st.expander("Description"):
            st.write(row.get("description", ""))