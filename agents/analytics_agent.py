def summarize_results(ranked_jobs):
    total = len(ranked_jobs)
    apply_count = sum(1 for job in ranked_jobs if job["recommendation"] == "Apply")
    avg_score = round(sum(job["match_score"] for job in ranked_jobs) / total, 2) if total else 0

    return {
        "total_jobs_found": total,
        "recommended_to_apply": apply_count,
        "average_match_score": avg_score
    }