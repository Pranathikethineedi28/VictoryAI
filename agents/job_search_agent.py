import re
import requests
import pandas as pd
import pycountry
import us
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_JOB_DESCRIPTION_CHARS = 5000
RECENT_WINDOW_HOURS = 72


TARGET_TERMS = [
    "data analyst",
    "business analyst",
    "business analytics",
    "product analyst",
    "product analytics",
    "analytics intern",
    "analytics analyst",
    "business intelligence",
    "bi analyst",
    "data scientist",
    "data science",
    "data science intern",
    "machine learning",
    "machine learning intern",
    "machine learning engineer",
    "ml engineer",
    "ai engineer",
    "ai data engineer",
    "data engineer",
    "decision science",
    "quantitative analyst",
    "research analyst",
]


LEVEL_TERMS = [
    "intern",
    "internship",
    "summer intern",
    "new grad",
    "new graduate",
    "university graduate",
    "graduate analyst",
    "entry level",
    "entry-level",
    "junior",
    "early career",
]


BAD_TITLE_TERMS = [
    "operations engineer",
    "supply chain",
    "software engineer",
    "systems analyst",
    "visual designer",
    "hardware design engineer",
    "adas",
    "vehicle parking",
    "procurement",
    "paid advertising",
    "video editor",
    "creative",
    "strategist",
    "frontier agents",
    "ai agent engineer",
    "enterprise ai development strategist",
    "cx reporting analyst",
    "sales",
    "marketing",
    "retail",
    "customer",
    "warehouse",
    "nurse",
    "technician",
    "mechanic",
    "driver",
    "legal",
    "law",
    "attorney",
    "financial advisor",
    "banker",
    "account executive",
    "account manager",
    "customer success",
    "customer support",
    "customer service",
    "store associate",
    "operations associate",
    "service associate",
    "content associate",
    "marketing associate",
    "recruiter",
    "talent acquisition",
    "manager",
    "senior",
    "sr.",
    "staff",
    "principal",
    "director",
    "lead",
    "head",
    "vp",
    "chief",
]


CLOSED_TERMS = [
    "no longer accepting applications",
    "this job is no longer available",
    "job has expired",
    "position has been filled",
    "this position is closed",
    "application deadline has passed",
]


US_STATES = set()
for state in us.states.STATES:
    US_STATES.add(state.name.lower())
    US_STATES.add(state.abbr.lower())


COUNTRIES = set()
for country in pycountry.countries:
    COUNTRIES.add(country.name.lower())
    if hasattr(country, "official_name"):
        COUNTRIES.add(country.official_name.lower())


def clean(text):
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_iso_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def is_recent(posted_date, max_hours=RECENT_WINDOW_HOURS):
    if not posted_date:
        return True

    posted = parse_iso_datetime(posted_date)

    if not posted:
        return True

    now = datetime.now(timezone.utc)

    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)

    hours = (now - posted).total_seconds() / 3600
    return 0 <= hours <= max_hours


def is_closed(description):
    text = clean(description).lower()
    return any(term in text for term in CLOSED_TERMS)


def is_us_location(location):
    loc = clean(location).lower()

    if not loc:
        return False

    if "united states" in loc or "usa" in loc:
        return True

    for state in US_STATES:
        if re.search(rf"\b{re.escape(state)}\b", loc):
            return True

    for country in COUNTRIES:
        if country == "united states":
            continue

        if re.search(rf"\b{re.escape(country)}\b", loc):
            return False

    return False


def has_bad_title(title):
    title_l = clean(title).lower()
    return any(term in title_l for term in BAD_TITLE_TERMS)


def relevance_bucket(title, description):
    title_l = clean(title).lower()
    desc_l = clean(description).lower()
    full_text = f"{title_l} {desc_l}"

    title_target = any(term in title_l for term in TARGET_TERMS)
    desc_target = any(term in desc_l for term in TARGET_TERMS)
    level_match = any(term in full_text for term in LEVEL_TERMS)

    if title_target:
        return "Strong Relevant"

    if desc_target and level_match:
        return "Possible Relevant"

    return "Irrelevant"


def keep_job(title, description, location):
    if has_bad_title(title):
        return False, "Rejected: bad title"

    if not is_us_location(location):
        return False, "Rejected: non-US or unknown location"

    if is_closed(description):
        return False, "Rejected: closed/expired"

    bucket = relevance_bucket(title, description)

    if bucket == "Irrelevant":
        return False, "Rejected: not target role"

    return True, bucket


def build_job_record(
    title,
    company,
    country,
    location,
    source,
    url,
    posted_date,
    description,
    ats,
    board_slug,
):
    description = clean(description)
    keep, bucket_or_reason = keep_job(title, description, location)

    if not keep:
        return None

    if posted_date and not is_recent(posted_date):
        return None

    return {
        "title": clean(title),
        "company": clean(company),
        "country": country or "USA",
        "location": clean(location),
        "source": source,
        "url": url,
        "posted_date": posted_date or "",
        "date_status": "Date Known" if posted_date else "Date Unknown",
        "ats": ats,
        "board_slug": board_slug,
        "relevance_bucket": bucket_or_reason,
        "recommendation": bucket_or_reason,
        "match_score": 0,
        "matched_skills": "",
        "role_category": bucket_or_reason,
        "level": "Detected from title/description",
        "match_reason": f"Kept by ATS filter: {bucket_or_reason}",
        "risk_flags": "",
        "description": description[:MAX_JOB_DESCRIPTION_CHARS],
    }


def fetch_greenhouse(company, slug):
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    jobs = []

    try:
        response = requests.get(api_url, timeout=20, headers={"User-Agent": "VictoryAI/2.0"})

        if response.status_code != 200:
            return jobs

        data = response.json()

        for job in data.get("jobs", []):
            title = job.get("title", "")
            description = clean(job.get("content", ""))
            location = ", ".join([office.get("name", "") for office in job.get("offices", [])])
            job_url = job.get("absolute_url", "")
            posted_date = job.get("updated_at", "")

            if not job_url:
                continue

            record = build_job_record(
                title=title,
                company=company,
                country="USA",
                location=location,
                source="Greenhouse",
                url=job_url,
                posted_date=posted_date,
                description=description,
                ats="greenhouse",
                board_slug=slug,
            )

            if record:
                jobs.append(record)

    except Exception as e:
        print(f"Greenhouse error ({company}): {e}")

    return jobs


def fetch_lever(company, slug):
    api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    jobs = []

    try:
        response = requests.get(api_url, timeout=20, headers={"User-Agent": "VictoryAI/2.0"})

        if response.status_code != 200:
            return jobs

        data = response.json()

        for job in data:
            title = job.get("text", "")
            description = clean(job.get("descriptionPlain", ""))
            location = job.get("categories", {}).get("location", "")
            job_url = job.get("hostedUrl", "")
            created_at = job.get("createdAt", "")

            posted_date = ""
            if created_at:
                try:
                    posted_date = datetime.fromtimestamp(
                        int(created_at) / 1000,
                        tz=timezone.utc,
                    ).isoformat()
                except Exception:
                    posted_date = ""

            if not job_url:
                continue

            record = build_job_record(
                title=title,
                company=company,
                country="USA",
                location=location,
                source="Lever",
                url=job_url,
                posted_date=posted_date,
                description=description,
                ats="lever",
                board_slug=slug,
            )

            if record:
                jobs.append(record)

    except Exception as e:
        print(f"Lever error ({company}): {e}")

    return jobs


def fetch_ashby(company, slug):
    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    jobs = []

    try:
        response = requests.get(api_url, timeout=20, headers={"User-Agent": "VictoryAI/2.0"})

        if response.status_code != 200:
            return jobs

        data = response.json()

        for job in data.get("jobs", []):
            title = job.get("title", "")
            description = clean(job.get("descriptionPlain", ""))
            location = job.get("location", "")
            job_url = job.get("jobUrl", "")
            posted_date = job.get("publishedAt", "")

            if not job_url:
                continue

            record = build_job_record(
                title=title,
                company=company,
                country="USA",
                location=location,
                source="Ashby",
                url=job_url,
                posted_date=posted_date,
                description=description,
                ats="ashby",
                board_slug=slug,
            )

            if record:
                jobs.append(record)

    except Exception as e:
        print(f"Ashby error ({company}): {e}")

    return jobs


def extract_generic_title(soup, fallback):
    h1 = soup.find("h1")
    if h1:
        return clean(h1.get_text(" ", strip=True))

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    return clean(title or fallback)


def extract_generic_location(text):
    text_l = clean(text).lower()

    state_matches = []
    for state in US_STATES:
        if len(state) == 2:
            if re.search(rf"\b{re.escape(state)}\b", text_l):
                state_matches.append(state.upper())
        else:
            if re.search(rf"\b{re.escape(state)}\b", text_l):
                state_matches.append(state.title())

    if state_matches:
        return ", ".join(sorted(set(state_matches))[:3])

    if "united states" in text_l:
        return "United States"

    if "usa" in text_l:
        return "USA"

    return ""


def is_likely_job_link(url):
    url_l = str(url or "").lower()

    bad = [
        "linkedin.com",
        "indeed.com",
        "glassdoor.com",
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "youtube.com",
        "privacy",
        "terms",
        "login",
        "signup",
    ]

    if any(x in url_l for x in bad):
        return False

    good = [
        "/job/",
        "/jobs/",
        "/careers/",
        "/positions/",
        "/opening",
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "workdayjobs.com",
    ]

    return any(x in url_l for x in good)


def fetch_generic_career_page(company, url):
    jobs = []

    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "VictoryAI/2.0"})

        if response.status_code != 200:
            return jobs

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = clean(soup.get_text(" ", strip=True))

        direct_title = extract_generic_title(soup, company)
        direct_location = extract_generic_location(page_text)

        direct_record = build_job_record(
            title=direct_title,
            company=company,
            country="USA",
            location=direct_location,
            source="Generic Career Page",
            url=url,
            posted_date="",
            description=page_text,
            ats="generic",
            board_slug=url,
        )

        if direct_record:
            jobs.append(direct_record)

        for a in soup.find_all("a", href=True):
            link_text = clean(a.get_text(" ", strip=True))
            href = urljoin(url, a.get("href", ""))

            if not is_likely_job_link(href):
                continue

            if not any(term in link_text.lower() for term in TARGET_TERMS):
                continue

            record = build_job_record(
                title=link_text,
                company=company,
                country="USA",
                location=direct_location,
                source="Generic Career Link",
                url=href,
                posted_date="",
                description=f"{link_text} {page_text[:2500]}",
                ats="generic",
                board_slug=url,
            )

            if record:
                jobs.append(record)

    except Exception as e:
        print(f"Generic career page error ({company}): {e}")

    return jobs


def fetch_smartrecruiters(company, slug):
    return []


def fetch_workday(company, slug):
    return fetch_generic_career_page(company, slug)


def fetch_icims(company, slug):
    return fetch_generic_career_page(company, slug)


def deduplicate_jobs(jobs):
    seen_urls = set()
    unique_jobs = []

    for job in jobs:
        url = str(job.get("url", "")).lower().strip()

        if not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)
        unique_jobs.append(job)

    return unique_jobs


def sort_jobs(jobs):
    bucket_priority = {
        "Strong Relevant": 0,
        "Possible Relevant": 1,
    }

    def sort_key(job):
        bucket = job.get("relevance_bucket", "Possible Relevant")
        posted_date = job.get("posted_date", "")
        parsed_date = parse_iso_datetime(posted_date)

        timestamp = 0

        if parsed_date:
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            timestamp = parsed_date.timestamp()

        return (
            bucket_priority.get(bucket, 9),
            -timestamp,
            job.get("company", ""),
            job.get("title", ""),
        )

    return sorted(jobs, key=sort_key)


def fetch_board_jobs(board):
    ats = str(board.get("ats", "")).lower().strip()
    company = board.get("company", "")
    slug = board.get("board_slug", "")

    if not ats or not slug:
        return ats, []

    try:
        if ats == "greenhouse":
            return ats, fetch_greenhouse(company, slug)

        if ats == "lever":
            return ats, fetch_lever(company, slug)

        if ats == "ashby":
            return ats, fetch_ashby(company, slug)

        if ats == "smartrecruiters":
            return ats, fetch_smartrecruiters(company, slug)

        if ats == "workday":
            return ats, fetch_workday(company, slug)

        if ats == "icims":
            return ats, fetch_icims(company, slug)

        if ats == "generic":
            return ats, fetch_generic_career_page(company, slug)

        return ats, []

    except Exception as e:
        print(f"Board fetch failed {ats} {company}: {e}")
        return ats, []


def search_jobs_from_boards(boards):
    all_jobs = []

    counts = {
        "greenhouse": 0,
        "lever": 0,
        "ashby": 0,
        "smartrecruiters": 0,
        "workday": 0,
        "icims": 0,
        "generic": 0,
    }

    print(f"Scanning ATS boards/pages in parallel: {len(boards)}")

    max_workers = 25

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_board_jobs, board)
            for board in boards
        ]

        for index, future in enumerate(as_completed(futures), start=1):
            ats, jobs = future.result()

            counts[ats] = counts.get(ats, 0) + len(jobs)
            all_jobs.extend(jobs)

            if index % 50 == 0:
                print(f"Scanned {index}/{len(boards)} boards... Jobs so far: {len(all_jobs)}")

    unique_jobs = deduplicate_jobs(all_jobs)
    sorted_jobs = sort_jobs(unique_jobs)

    for source, count in counts.items():
        print(f"{source} jobs kept: {count}")

    strong_count = sum(
        1 for job in sorted_jobs
        if job.get("relevance_bucket") == "Strong Relevant"
    )

    possible_count = sum(
        1 for job in sorted_jobs
        if job.get("relevance_bucket") == "Possible Relevant"
    )

    print(f"Clean relevant jobs found: {len(sorted_jobs)}")
    print(f"Strong Relevant: {strong_count}")
    print(f"Possible Relevant: {possible_count}")

    return pd.DataFrame(sorted_jobs)

    for board in boards:
        ats = str(board.get("ats", "")).lower().strip()
        company = board.get("company", "")
        slug = board.get("board_slug", "")

        if not ats or not slug:
            continue

        if ats == "greenhouse":
            jobs = fetch_greenhouse(company, slug)
        elif ats == "lever":
            jobs = fetch_lever(company, slug)
        elif ats == "ashby":
            jobs = fetch_ashby(company, slug)
        elif ats == "smartrecruiters":
            jobs = fetch_smartrecruiters(company, slug)
        elif ats == "workday":
            jobs = fetch_workday(company, slug)
        elif ats == "icims":
            jobs = fetch_icims(company, slug)
        elif ats == "generic":
            jobs = fetch_generic_career_page(company, slug)
        else:
            jobs = []

        counts[ats] = counts.get(ats, 0) + len(jobs)
        all_jobs.extend(jobs)

    unique_jobs = deduplicate_jobs(all_jobs)
    sorted_jobs = sort_jobs(unique_jobs)

    for source, count in counts.items():
        print(f"{source} jobs kept: {count}")

    strong_count = sum(
        1 for job in sorted_jobs if job.get("relevance_bucket") == "Strong Relevant"
    )

    possible_count = sum(
        1 for job in sorted_jobs if job.get("relevance_bucket") == "Possible Relevant"
    )

    print(f"Clean relevant jobs found: {len(sorted_jobs)}")
    print(f"Strong Relevant: {strong_count}")
    print(f"Possible Relevant: {possible_count}")

    return pd.DataFrame(sorted_jobs)