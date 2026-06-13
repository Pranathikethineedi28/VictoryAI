MIN_ATS_SCORE = 70


def rank_jobs(jobs_df, profile):
    if jobs_df is None or jobs_df.empty:
        return []

    skills = [str(s).lower() for s in profile.get("skills", [])]

    good_role_terms = [
        "data analyst",
        "business analyst",
        "business analytics",
        "product analyst",
        "data scientist",
        "data science",
        "machine learning",
        "ml engineer",
        "ai engineer",
        "artificial intelligence",
        "genai",
        "generative ai",
        "analytics",
        "business intelligence",
        "bi analyst",
        "decision science",
        "data engineer",
    ]

    level_terms = [
        "intern",
        "internship",
        "summer intern",
        "new grad",
        "new graduate",
        "entry level",
        "entry-level",
        "junior",
        "early career",
        "university graduate",
        "graduate analyst",
    ]

    bad_title_terms = [
        "senior",
        "sr.",
        "staff",
        "principal",
        "manager",
        "director",
        "lead",
        "head",
        "vp",
        "chief",
        "sales",
        "account executive",
        "customer service",
        "retail",
        "cashier",
        "store",
        "warehouse",
        "driver",
        "nurse",
        "technician",
        "mechanic",
        "legal",
        "law",
        "attorney",
        "financial advisor",
        "banker",
        "operations associate",
        "service associate",
        "content associate",
        "marketing associate",
    ]

    strong_skills = [
        "python",
        "sql",
        "excel",
        "power bi",
        "tableau",
        "pandas",
        "numpy",
        "scikit-learn",
        "machine learning",
        "statistics",
        "analytics",
        "data analysis",
        "business intelligence",
        "dashboard",
        "forecasting",
        "a/b testing",
        "etl",
        "snowflake",
        "azure",
        "rag",
        "langchain",
        "faiss",
    ]

    ranked = []

    for _, row in jobs_df.iterrows():
        job = row.to_dict()

        title = str(job.get("title", "")).lower()
        description = str(job.get("description", "")).lower()
        location = str(job.get("location", "")).lower()
        source = str(job.get("source", "")).lower()

        full_text = f"{title} {description}"

        if any(bad in title for bad in bad_title_terms):
            continue

        role_match = any(term in full_text for term in good_role_terms)
        level_match = any(term in full_text for term in level_terms)

        score = 0
        reasons = []

        if any(term in title for term in good_role_terms):
            score += 35
            reasons.append("Target role found in title")
        elif any(term in description for term in good_role_terms):
            score += 20
            reasons.append("Target role found in description")

        if any(term in title for term in level_terms):
            score += 25
            reasons.append("Intern/new-grad/entry-level match")

        matched_profile_skills = [
            skill for skill in skills
            if skill and skill in full_text
        ]

        matched_strong_skills = [
            skill for skill in strong_skills
            if skill in full_text
        ]

        score += min(len(set(matched_profile_skills)) * 4, 20)
        score += min(len(set(matched_strong_skills)) * 3, 15)

        all_matched_skills = sorted(set(matched_profile_skills + matched_strong_skills))

        if all_matched_skills:
            reasons.append("Skills matched: " + ", ".join(all_matched_skills[:8]))

        if any(loc in location for loc in [
            "new york",
            "new jersey",
            "jersey city",
            "remote",
            "united states",
            "usa",
            "u.s."
        ]):
            score += 5
            reasons.append("USA/preferred location")

        if any(src in source for src in [
            "greenhouse",
            "lever",
            "ashby",
            "smartrecruiters",
            "workday",
            "direct"
        ]):
            score += 5
            reasons.append("Direct career/ATS source")

        score = min(score, 100)

        if score >= 90:
            recommendation = "Perfect Match"
        elif score >= 80:
            recommendation = "Strong Apply"
        elif score >= MIN_ATS_SCORE:
            recommendation = "Apply"
        elif score >= 60:
            recommendation = "Review"
        else:
            recommendation = "Low Priority"

        job["match_score"] = score
        job["ats_match"] = score
        job["recommended"] = score >= MIN_ATS_SCORE
        job["recommendation"] = recommendation
        job["matched_skills"] = ", ".join(all_matched_skills)
        job["match_reason"] = "; ".join(reasons)

        ranked.append(job)

    ranked = sorted(
        ranked,
        key=lambda x: int(x.get("match_score", 0) or 0),
        reverse=True
    )

    return ranked