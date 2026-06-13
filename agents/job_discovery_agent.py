import os
import re
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

QUERIES = [
    # Greenhouse
    'site:boards.greenhouse.io "Data Analyst Intern"',
    'site:boards.greenhouse.io "Business Analyst Intern"',
    'site:boards.greenhouse.io "Product Analyst Intern"',
    'site:boards.greenhouse.io "Data Science Intern"',
    'site:boards.greenhouse.io "Machine Learning Intern"',
    'site:boards.greenhouse.io "AI Intern"',
    'site:boards.greenhouse.io "New Grad Data"',
    'site:boards.greenhouse.io "Entry Level Data"',
    'site:boards.greenhouse.io "Business Intelligence Intern"',

    # Lever
    'site:jobs.lever.co "Data Analyst Intern"',
    'site:jobs.lever.co "Business Analyst Intern"',
    'site:jobs.lever.co "Product Analyst Intern"',
    'site:jobs.lever.co "Data Science Intern"',
    'site:jobs.lever.co "Machine Learning Intern"',
    'site:jobs.lever.co "AI Intern"',
    'site:jobs.lever.co "New Grad Data"',
    'site:jobs.lever.co "Entry Level Data"',
    'site:jobs.lever.co "Business Intelligence Intern"',

    # Ashby
    'site:jobs.ashbyhq.com "Data Analyst Intern"',
    'site:jobs.ashbyhq.com "Business Analyst Intern"',
    'site:jobs.ashbyhq.com "Product Analyst Intern"',
    'site:jobs.ashbyhq.com "Data Science Intern"',
    'site:jobs.ashbyhq.com "Machine Learning Intern"',
    'site:jobs.ashbyhq.com "AI Intern"',
    'site:jobs.ashbyhq.com "New Grad Data"',
    'site:jobs.ashbyhq.com "Entry Level Data"',
    'site:jobs.ashbyhq.com "Business Intelligence Intern"',

    # SmartRecruiters
    'site:jobs.smartrecruiters.com "Data Analyst Intern"',
    'site:jobs.smartrecruiters.com "Business Analyst Intern"',
    'site:jobs.smartrecruiters.com "Product Analyst Intern"',
    'site:jobs.smartrecruiters.com "Data Science Intern"',
    'site:jobs.smartrecruiters.com "Machine Learning Intern"',

    # Workday
    'site:myworkdayjobs.com "Data Analyst Intern"',
    'site:myworkdayjobs.com "Business Analyst Intern"',
    'site:myworkdayjobs.com "Product Analyst Intern"',
    'site:myworkdayjobs.com "Data Science Intern"',
    'site:myworkdayjobs.com "Machine Learning Intern"',

    # iCIMS
    'site:icims.com "Data Analyst Intern"',
    'site:icims.com "Business Analyst Intern"',
    'site:icims.com "Product Analyst Intern"',
    'site:icims.com "Data Science Intern"',

    # Generic company career pages
    '"Data Analyst Intern" "United States" "careers"',
    '"Business Analyst Intern" "United States" "careers"',
    '"Product Analyst Intern" "United States" "careers"',
    '"Data Science Intern" "United States" "careers"',
    '"Machine Learning Intern" "United States" "careers"',
    '"AI Intern" "United States" "careers"',
    '"Entry Level Data Analyst" "United States" "careers"',
    '"New Grad Data Scientist" "United States" "careers"',

    '"Data Analyst Intern" "United States" "jobs"',
    '"Business Analyst Intern" "United States" "jobs"',
    '"Product Analyst Intern" "United States" "jobs"',
    '"Data Science Intern" "United States" "jobs"',
    '"Machine Learning Intern" "United States" "jobs"',
    '"AI Intern" "United States" "jobs"',
    '"Entry Level Data Analyst" "United States" "jobs"',
    '"New Grad Machine Learning Engineer" "United States" "jobs"',
]


BLOCKED_DOMAINS = [
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "simplyhired.com",
    "dice.com",
    "careerbuilder.com",
    "lensa.com",
    "jooble.org",
    "talent.com",
    "facebook.com",
    "reddit.com",
    "youtube.com",
    "instagram.com",
]


def is_blocked_url(url):
    url_l = str(url or "").lower()
    return any(domain in url_l for domain in BLOCKED_DOMAINS)


def clean_company_slug(slug):
    return (
        str(slug or "")
        .replace("-", " ")
        .replace("_", " ")
        .replace("careers", "")
        .replace("jobs", "")
        .strip()
        .title()
    )


def detect_board(url):
    if not url or is_blocked_url(url):
        return None

    parsed = urlparse(url)
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    parts = [p for p in path.strip("/").split("/") if p]

    ats = None
    board_slug = None
    company = None

    if "boards.greenhouse.io" in netloc and parts:
        ats = "greenhouse"
        board_slug = parts[0]
        company = clean_company_slug(board_slug)

    elif "jobs.lever.co" in netloc and parts:
        ats = "lever"
        board_slug = parts[0]
        company = clean_company_slug(board_slug)

    elif "jobs.ashbyhq.com" in netloc and parts:
        ats = "ashby"
        board_slug = parts[0]
        company = clean_company_slug(board_slug)

    elif "jobs.smartrecruiters.com" in netloc and parts:
        ats = "smartrecruiters"
        board_slug = parts[0]
        company = clean_company_slug(board_slug)

    elif "myworkdayjobs.com" in netloc:
        ats = "workday"
        board_slug = url
        company = clean_company_slug(netloc.split(".")[0])

    elif "icims.com" in netloc:
        ats = "icims"
        board_slug = url
        company = clean_company_slug(netloc.split(".")[0])

    elif "/careers" in path.lower() or "/jobs" in path.lower() or "/job/" in path.lower():
        ats = "generic"
        board_slug = url
        company = clean_company_slug(netloc.split(".")[0])

    else:
        return None

    return {
        "ats": ats,
        "board_slug": board_slug,
        "company": company,
        "source_url": url,
    }


def discover_company_boards(max_results_per_query=50):
    boards = []

    for query in QUERIES:
        print(f"Discovering boards: {query}")

        try:
            response = client.search(
                query=query,
                max_results=max_results_per_query,
                search_depth="advanced",
                include_answer=False,
                include_raw_content=False,
            )

            for result in response.get("results", []):
                url = result.get("url", "")
                board = detect_board(url)

                if board:
                    boards.append(board)

        except Exception as e:
            print(f"Tavily error: {e}")

    unique = {}

    for board in boards:
        key = f"{board['ats']}::{board['board_slug']}".lower()
        unique[key] = board

    boards = list(unique.values())

    print(f"Discovered unique boards/pages: {len(boards)}")

    counts = {}
    for board in boards:
        ats = board.get("ats", "unknown")
        counts[ats] = counts.get(ats, 0) + 1

    for ats, count in counts.items():
        print(f"{ats}: {count}")

    return boards