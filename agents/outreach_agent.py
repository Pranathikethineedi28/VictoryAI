def generate_outreach(profile, job):
    name = profile.get("name", "Pranathi")

    return f"""
Hi,

I hope you're doing well. I came across the {job['title']} role at {job['company']} and was very interested.

I am currently pursuing a Master's in Business Analytics and AI, with experience in Python, SQL, dashboards, machine learning, and AI systems. My recent work includes RAG systems, analytics automation, and business intelligence projects.

I would love to connect and learn more about this opportunity.

Best,
{name}
"""