import os
import json
from datetime import datetime, timezone, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

from agents.job_discovery_agent import discover_company_boards
from agents.job_search_agent import search_jobs_from_boards
from agents.outreach_agent import generate_outreach

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
APPLICATIONS_PATH = os.path.join(DATA_DIR, "applications.csv")
OUTREACH_PATH = os.path.join(DATA_DIR, "outreach.csv")
SUMMARY_PATH = os.path.join(OUTPUTS_DIR, "run_summary.json")

DATABASE_URL = os.getenv("DATABASE_URL")

RECENT_HOURS = 24
MIN_EMBEDDING_SCORE = 25
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def now_utc():
    return datetime.now(timezone.utc)


def now_iso():
    return now_utc().isoformat()


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)


def connect_db():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL missing.")

    conn = psycopg2.connect(DATABASE_URL)

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS boards (
                id SERIAL PRIMARY KEY,
                ats TEXT,
                board_slug TEXT,
                company TEXT,
                source_url TEXT,
                first_seen_at TIMESTAMPTZ DEFAULT NOW(),
                last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(ats, board_slug)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs_seen (
                url TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                source TEXT,
                first_seen_at TIMESTAMPTZ,
                last_seen_at TIMESTAMPTZ,
                seen_count INTEGER DEFAULT 1
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                url TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                country TEXT,
                source TEXT,
                posted_date TEXT,
                date_status TEXT,
                relevance_bucket TEXT,
                embedding_score REAL,
                match_score REAL,
                recommendation TEXT,
                matched_skills TEXT,
                role_category TEXT,
                level TEXT,
                match_reason TEXT,
                risk_flags TEXT,
                description TEXT,
                outreach_message TEXT,
                first_seen_at TIMESTAMPTZ,
                last_seen_at TIMESTAMPTZ,
                is_new_24h BOOLEAN,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id SERIAL PRIMARY KEY,
                run_started_at TIMESTAMPTZ,
                run_finished_at TIMESTAMPTZ,
                clean_jobs_found INTEGER,
                new_jobs_last_24h INTEGER,
                total_saved_jobs INTEGER,
                average_embedding_score NUMERIC,
                status TEXT
            );
        """)

        conn.commit()

    return conn


def load_profile():
    if not os.path.exists(PROFILE_PATH):
        profile = {
            "target_roles": [
                "AI Engineer",
                "Machine Learning Engineer",
                "Data Scientist",
                "Data Analyst",
                "Business Analyst",
                "Product Analyst",
                "Business Intelligence Analyst"
            ],
            "skills": [
                "Python",
                "SQL",
                "Machine Learning",
                "Data Analytics",
                "Business Analytics",
                "Power BI",
                "Tableau",
                "PostgreSQL",
                "LLMs",
                "RAG",
                "LangChain",
                "FAISS",
                "Azure OpenAI"
            ],
            "projects": [
                "VictoryAI job intelligence platform",
                "RAG system",
                "Netflix analytics project"
            ],
            "experience": [
                "Business Analytics",
                "AI",
                "Data Engineering"
            ],
            "education": [
                "MS Business Analytics and Artificial Intelligence"
            ]
        }

        os.makedirs(DATA_DIR, exist_ok=True)

        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        return profile

    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_boards_to_postgres(boards):
    if not boards:
        return 0

    conn = connect_db()
    saved = 0

    with conn.cursor() as cur:
        for board in boards:
            ats = board.get("ats", "")
            board_slug = board.get("board_slug", "")
            company = board.get("company", "")
            source_url = board.get("source_url", "")

            if not ats or not board_slug:
                continue

            cur.execute("""
                INSERT INTO boards (
                    ats,
                    board_slug,
                    company,
                    source_url,
                    last_seen_at
                )
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (ats, board_slug)
                DO UPDATE SET
                    company = EXCLUDED.company,
                    source_url = EXCLUDED.source_url,
                    last_seen_at = NOW();
            """, (
                ats,
                board_slug,
                company,
                source_url
            ))

            saved += 1

    conn.commit()
    conn.close()

    print(f"Saved/updated boards in PostgreSQL: {saved}")
    return saved


def load_boards_from_postgres():
    conn = connect_db()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT ats, board_slug, company, source_url
            FROM boards
            ORDER BY last_seen_at DESC;
        """)

        rows = cur.fetchall()

    conn.close()

    boards = [dict(row) for row in rows]

    print(f"Loaded cached boards from PostgreSQL: {len(boards)}")
    return boards


def get_boards():
    print("Discovering boards with Tavily...")

    try:
        boards = discover_company_boards(max_results_per_query=100)
    except Exception as e:
        print(f"Tavily discovery failed: {e}")
        boards = []

    if boards:
        save_boards_to_postgres(boards)
        return boards

    print("No boards discovered from Tavily. Falling back to cached PostgreSQL boards.")
    return load_boards_from_postgres()


def build_profile_text(profile):
    parts = []

    for key in ["target_roles", "skills", "projects", "experience", "education"]:
        value = profile.get(key, "")

        if isinstance(value, list):
            parts.extend([str(x) for x in value])
        elif isinstance(value, dict):
            parts.append(json.dumps(value))
        else:
            parts.append(str(value))

    return " ".join(parts)


def build_job_text(job):
    return f"""
Title: {job.get("title", "")}
Company: {job.get("company", "")}
Location: {job.get("location", "")}
Source: {job.get("source", "")}
Relevance: {job.get("relevance_bucket", "")}
Description: {str(job.get("description", ""))[:4000]}
"""


def embedding_score_jobs(jobs, profile):
    if not jobs:
        return []

    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    profile_text = build_profile_text(profile)
    job_texts = [build_job_text(job) for job in jobs]

    print("Computing embedding match scores...")

    profile_embedding = model.encode([profile_text])
    job_embeddings = model.encode(job_texts)

    similarities = cosine_similarity(profile_embedding, job_embeddings)[0]

    scored_jobs = []

    for job, sim in zip(jobs, similarities):
        score = round(float(sim) * 100, 2)

        job["embedding_score"] = score
        job["match_score"] = score

        if score >= 75:
            job["recommendation"] = "Strong Match"
        elif score >= 60:
            job["recommendation"] = "Good Match"
        elif score >= MIN_EMBEDDING_SCORE:
            job["recommendation"] = "Possible Match"
        else:
            job["recommendation"] = "Low Match"

        job["match_reason"] = "Semantic embedding similarity between profile and job."
        scored_jobs.append(job)

    return sorted(
        scored_jobs,
        key=lambda x: float(x.get("embedding_score", 0) or 0),
        reverse=True
    )


def is_recent_first_seen(first_seen_at):
    try:
        if isinstance(first_seen_at, str):
            first_seen = datetime.fromisoformat(first_seen_at.replace("Z", "+00:00"))
        else:
            first_seen = first_seen_at

        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)

        return first_seen >= now_utc() - timedelta(hours=RECENT_HOURS)
    except Exception:
        return False


def update_seen_memory(jobs):
    conn = connect_db()
    recent_jobs = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for job in jobs:
            url = str(job.get("url", "")).strip()

            if not url:
                continue

            cur.execute(
                "SELECT first_seen_at, seen_count FROM jobs_seen WHERE url = %s",
                (url,)
            )

            existing = cur.fetchone()
            current_time = now_utc()

            if existing:
                first_seen_at = existing["first_seen_at"]
                seen_count = existing["seen_count"] or 0

                cur.execute("""
                    UPDATE jobs_seen
                    SET last_seen_at = %s,
                        seen_count = %s,
                        title = %s,
                        company = %s,
                        location = %s,
                        source = %s
                    WHERE url = %s
                """, (
                    current_time,
                    seen_count + 1,
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("source", ""),
                    url
                ))

                job["first_seen_at"] = first_seen_at
                job["last_seen_at"] = current_time
                job["is_new_24h"] = is_recent_first_seen(first_seen_at)

            else:
                cur.execute("""
                    INSERT INTO jobs_seen (
                        url,
                        title,
                        company,
                        location,
                        source,
                        first_seen_at,
                        last_seen_at,
                        seen_count
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    url,
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("source", ""),
                    current_time,
                    current_time,
                    1
                ))

                job["first_seen_at"] = current_time
                job["last_seen_at"] = current_time
                job["is_new_24h"] = True

            if job["is_new_24h"]:
                recent_jobs.append(job)

    conn.commit()
    conn.close()

    return recent_jobs


def save_jobs_to_postgres(jobs):
    if not jobs:
        return 0

    conn = connect_db()
    saved = 0

    with conn.cursor() as cur:
        for job in jobs:
            url = str(job.get("url", "")).strip()

            if not url:
                continue

            cur.execute("""
                INSERT INTO jobs (
                    url,
                    title,
                    company,
                    location,
                    country,
                    source,
                    posted_date,
                    date_status,
                    relevance_bucket,
                    embedding_score,
                    match_score,
                    recommendation,
                    matched_skills,
                    role_category,
                    level,
                    match_reason,
                    risk_flags,
                    description,
                    outreach_message,
                    first_seen_at,
                    last_seen_at,
                    is_new_24h,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, NOW()
                )
                ON CONFLICT (url)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    country = EXCLUDED.country,
                    source = EXCLUDED.source,
                    posted_date = EXCLUDED.posted_date,
                    date_status = EXCLUDED.date_status,
                    relevance_bucket = EXCLUDED.relevance_bucket,
                    embedding_score = EXCLUDED.embedding_score,
                    match_score = EXCLUDED.match_score,
                    recommendation = EXCLUDED.recommendation,
                    matched_skills = EXCLUDED.matched_skills,
                    role_category = EXCLUDED.role_category,
                    level = EXCLUDED.level,
                    match_reason = EXCLUDED.match_reason,
                    risk_flags = EXCLUDED.risk_flags,
                    description = EXCLUDED.description,
                    outreach_message = EXCLUDED.outreach_message,
                    last_seen_at = EXCLUDED.last_seen_at,
                    is_new_24h = EXCLUDED.is_new_24h,
                    updated_at = NOW();
            """, (
                url,
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("country", "USA"),
                job.get("source", ""),
                job.get("posted_date", ""),
                job.get("date_status", ""),
                job.get("relevance_bucket", ""),
                float(job.get("embedding_score", 0) or 0),
                float(job.get("match_score", 0) or 0),
                job.get("recommendation", ""),
                job.get("matched_skills", ""),
                job.get("role_category", ""),
                job.get("level", ""),
                job.get("match_reason", ""),
                job.get("risk_flags", ""),
                job.get("description", ""),
                job.get("outreach_message", ""),
                job.get("first_seen_at"),
                job.get("last_seen_at"),
                bool(job.get("is_new_24h", False)),
            ))

            saved += 1

    conn.commit()
    conn.close()

    print(f"Saved/updated jobs in PostgreSQL: {saved}")
    return saved


def add_outreach(jobs, profile):
    print("Generating outreach messages...")

    enriched = []

    for job in jobs:
        try:
            job["outreach_message"] = generate_outreach(profile, job)
        except Exception:
            job["outreach_message"] = ""

        enriched.append(job)

    return enriched


def save_outputs(jobs):
    df = pd.DataFrame(jobs)

    if df.empty:
        df = pd.DataFrame(columns=[
            "title",
            "company",
            "country",
            "location",
            "source",
            "url",
            "posted_date",
            "date_status",
            "first_seen_at",
            "last_seen_at",
            "is_new_24h",
            "relevance_bucket",
            "embedding_score",
            "match_score",
            "recommendation",
            "matched_skills",
            "role_category",
            "level",
            "match_reason",
            "risk_flags",
            "description",
            "outreach_message"
        ])

    df.to_csv(APPLICATIONS_PATH, index=False, encoding="utf-8")

    outreach_cols = [
        col for col in ["company", "title", "location", "url", "outreach_message"]
        if col in df.columns
    ]

    if outreach_cols:
        df[outreach_cols].to_csv(OUTREACH_PATH, index=False, encoding="utf-8")

    return df


def save_run_to_postgres(summary):
    conn = connect_db()

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO workflow_runs (
                run_started_at,
                run_finished_at,
                clean_jobs_found,
                new_jobs_last_24h,
                total_saved_jobs,
                average_embedding_score,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            summary["run_started_at"],
            summary["run_finished_at"],
            summary["clean_jobs_found"],
            summary["new_jobs_last_24h"],
            summary["total_saved_jobs"],
            summary["average_embedding_score"],
            summary["status"]
        ))

    conn.commit()
    conn.close()


def save_summary(jobs, all_clean_count, df, started_at):
    scores = [float(job.get("embedding_score", 0) or 0) for job in jobs]

    recommended = [
        job for job in jobs
        if job.get("recommendation") in [
            "Strong Match",
            "Good Match",
            "Possible Match"
        ]
    ]

    summary = {
        "clean_jobs_found": all_clean_count,
        "new_jobs_last_24h": len(jobs),
        "total_jobs_found": len(jobs),
        "recommended_to_apply": len(recommended),
        "average_embedding_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "total_saved_jobs": len(df),
        "run_started_at": started_at,
        "run_finished_at": now_iso(),
        "status": "SUCCESS",
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    save_run_to_postgres(summary)

    print(summary)


def main():
    ensure_dirs()

    started_at = now_iso()

    print("=" * 80)
    print("VictoryAI Production Pipeline Started")
    print("=" * 80)

    profile = load_profile()

    boards = get_boards()

    if not boards:
        print("No boards available from Tavily or PostgreSQL cache.")
        df = save_outputs([])
        save_summary([], 0, df, started_at)
        return

    jobs_df = search_jobs_from_boards(boards)

    if jobs_df.empty:
        print("No clean jobs found.")
        df = save_outputs([])
        save_summary([], 0, df, started_at)
        return

    all_clean_jobs = jobs_df.to_dict("records")

    print(f"Clean jobs found: {len(all_clean_jobs)}")
    print("Updating PostgreSQL first_seen_at memory...")

    recent_jobs = update_seen_memory(all_clean_jobs)

    print(f"New jobs discovered in last {RECENT_HOURS}h: {len(recent_jobs)}")

    scored_jobs = embedding_score_jobs(recent_jobs, profile)

    final_jobs = add_outreach(scored_jobs, profile)

    save_jobs_to_postgres(final_jobs)

    df = save_outputs(final_jobs)

    print("=" * 80)
    print("VictoryAI Production Pipeline Finished")
    print("=" * 80)

    save_summary(final_jobs, len(all_clean_jobs), df, started_at)


if __name__ == "__main__":
    main()