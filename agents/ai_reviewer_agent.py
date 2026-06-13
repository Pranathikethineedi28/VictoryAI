import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
client = TavilyClient(api_key=TAVILY_API_KEY)

SEARCH_QUERIES = [
    '"Data Analyst Intern" "posted" "United States" "apply"',
    '"Business Analyst Intern" "posted" "United States" "apply"',
    '"Product Analyst Intern" "posted" "United States" "apply"',
    '"Data Science Intern" "posted" "United States" "apply"',
    '"Machine Learning Intern" "posted" "United States" "apply"',
    '"AI Intern" "posted" "United States" "apply"',
    '"Entry Level Data Analyst" "posted" "United States" "apply"',
    '"New Grad Data Scientist" "posted" "United States" "apply"',
    '"New Grad Machine Learning Engineer" "posted" "United States" "apply"',

    'site:boards.greenhouse.io "Data Analyst Intern" "United States"',
    'site:jobs.lever.co "Data Analyst Intern" "United States"',
    'site:jobs.ashbyhq.com "Data Analyst Intern" "United States"',
    'site:myworkdayjobs.com "Data Analyst Intern" "United States"',
    'site:smartrecruiters.com "Data Analyst Intern" "United States"',
    'site:icims.com "Data Analyst Intern" "United States"',
]

BLOCKED_URL_PATTERNS = [
    "linkedin.com/jobs/search",
    "linkedin.com/jobs/collections",
    "dice.com/jobs",
    "indeed.com/jobs",
    "ziprecruiter.com/jobs",
    "glassdoor.com/job",
    "simplyhired.com/search",
    "builtin.com/jobs",
    "monster.com/jobs",
    "careerbuilder.com/jobs",
    "jooble.org",
    "talent.com",
    "lensa.com",
    "google.com/search",
    "/search?",
    "/jobs?",
    "blog",
    "article",
    "best-",
    "top-",
]

GOOD_JOB_URL_PATTERNS = [
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "icims.com",
    "workable.com",
    "bamboohr.com",
    "jobvite.com",
    "rippling.com",
    "careers.",
    "/careers/",
    "/jobs/",
    "/job/",
    "/apply/",
]


def is_direct_job_url(url):
    url = str(url or "").lower()

    if not url:
        return False

    if any(blocked in url for blocked in BLOCKED_URL_PATTERNS):
        return False

    return any(good in url for good in GOOD_JOB_URL_PATTERNS)


def discover_job_urls(max_results_per_query=20):
    if not TAVILY_API_KEY:
        raise ValueError("Missing TAVILY_API_KEY in .env")

    discovered = []

    for query in SEARCH_QUERIES:
        print(f"Discovering: {query}")

        try:
            response = client.search(
                query=query,
                max_results=max_results_per_query,
                search_depth="advanced",
                include_answer=False,
                include_raw_content=False
            )

            for result in response.get("results", []):
                url = result.get("url", "")
                title = result.get("title", "")
                snippet = result.get("content", "")

                if is_direct_job_url(url):
                    discovered.append({
                        "source_query": query,
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })

        except Exception as e:
            print(f"Tavily failed for query: {query} | {e}")

    seen = set()
    unique = []

    for item in discovered:
        url = item["url"].strip()

        if url not in seen:
            seen.add(url)
            unique.append(item)

    print(f"Unique direct job URLs discovered: {len(unique)}")
    return unique