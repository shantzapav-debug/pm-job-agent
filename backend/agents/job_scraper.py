"""
Job scraper agent — scrapes PM jobs from Naukri, LinkedIn, Indeed.
Returns list of raw job dicts for the pipeline.
"""
import requests
import json
import re
import time
import logging
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─────────────────────────── NAUKRI ────────────────────────────

def scrape_naukri(keyword: str = "product manager", location: str = "bengaluru", pages: int = 5) -> list[dict]:
    jobs = []
    session = requests.Session()
    session.headers.update({
        **HEADERS,
        "appid": "109",
        "systemid": "109",
    })

    for page in range(1, pages + 1):
        url = (
            f"https://www.naukri.com/jobapi/v3/search"
            f"?noOfResults=20&urlType=search_by_keyword&searchType=adv"
            f"&keyword={keyword.replace(' ', '+')}&location={location}"
            f"&experience=3&pageNo={page}&k={keyword.replace(' ', '%20')}&l={location}"
            f"&freshness=1"  # last 24 hours only
        )
        try:
            resp = session.get(url, timeout=15)
            data = resp.json()
            job_list = data.get("jobDetails", [])
            for j in job_list:
                job_id = str(j.get("jobId", ""))
                title = j.get("title", "")
                company = j.get("companyName", "")
                loc = ", ".join(j.get("placeholders", [{}])[0].get("label", "").split(",")[:2]) if j.get("placeholders") else location
                url_link = j.get("jdURL", "")
                if url_link and not url_link.startswith("http"):
                    url_link = "https://www.naukri.com" + url_link
                exp = j.get("experience", {}).get("label", "")
                salary = j.get("salary", {}).get("label", "Not disclosed")
                posted = j.get("footerPlaceholderLabel", "")
                skills = [s.get("label", "") for s in j.get("tagsAndSkills", [])]
                description = j.get("jobDescription", "")

                if not title or not company:
                    continue

                jobs.append({
                    "source": "naukri",
                    "job_id_external": f"naukri_{job_id}",
                    "title": title,
                    "company": company,
                    "location": loc or location,
                    "job_url": url_link,
                    "experience_required": exp,
                    "salary_range": salary,
                    "posted_date": posted,
                    "skills_required": skills,
                    "description": description[:3000],
                })
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Naukri page {page} error: {e}")

    return jobs


# ─────────────────────────── LINKEDIN ──────────────────────────

def scrape_linkedin(keyword: str = "product manager", location: str = "Bengaluru", pages: int = 2) -> list[dict]:
    jobs = []
    base = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    for start in range(0, pages * 25, 25):
        params = {
            "keywords": keyword,
            "location": location,
            "geoId": "105556991",  # Bengaluru, Karnataka, India
            "trk": "public_jobs_jobs-search-bar_search-submit",
            "position": 1,
            "pageNum": 0,
            "start": start,
        }
        try:
            resp = requests.get(base, params=params, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")
            for card in cards:
                try:
                    job_id = card.find("div", {"data-entity-urn": True})
                    if not job_id:
                        continue
                    urn = job_id["data-entity-urn"]
                    jid = urn.split(":")[-1]

                    title_el = card.find("h3", class_=re.compile("base-search-card__title"))
                    company_el = card.find("h4", class_=re.compile("base-search-card__subtitle"))
                    loc_el = card.find("span", class_=re.compile("job-search-card__location"))
                    link_el = card.find("a", href=True)
                    posted_el = card.find("time")

                    title = title_el.get_text(strip=True) if title_el else ""
                    company = company_el.get_text(strip=True) if company_el else ""
                    loc = loc_el.get_text(strip=True) if loc_el else location
                    link = link_el["href"].split("?")[0] if link_el else ""
                    posted = posted_el.get("datetime", "") if posted_el else ""

                    if not title or not company:
                        continue

                    # Fetch JD
                    description, skills = _fetch_linkedin_jd(jid)

                    jobs.append({
                        "source": "linkedin",
                        "job_id_external": f"linkedin_{jid}",
                        "title": title,
                        "company": company,
                        "location": loc,
                        "job_url": link,
                        "experience_required": "",
                        "salary_range": "Not disclosed",
                        "posted_date": posted,
                        "skills_required": skills,
                        "description": description[:3000],
                    })
                except Exception:
                    continue
            time.sleep(1.5)
        except Exception as e:
            logger.warning(f"LinkedIn page start={start} error: {e}")

    return jobs


def _fetch_linkedin_jd(job_id: str) -> tuple[str, list]:
    try:
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        desc_el = soup.find("div", class_=re.compile("description__text"))
        desc = desc_el.get_text(separator="\n", strip=True) if desc_el else ""
        criteria = soup.find_all("li", class_=re.compile("description__job-criteria-item"))
        skills = [c.find("span", class_=re.compile("description__job-criteria-text")).get_text(strip=True)
                  for c in criteria if c.find("span", class_=re.compile("description__job-criteria-text"))]
        return desc[:3000], skills
    except Exception:
        return "", []


# ─────────────────────────── INDEED ────────────────────────────

def scrape_indeed(keyword: str = "product manager", location: str = "Bengaluru, Karnataka", pages: int = 2) -> list[dict]:
    jobs = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for start in range(0, pages * 10, 10):
        url = (
            f"https://in.indeed.com/jobs"
            f"?q={keyword.replace(' ', '+')}"
            f"&l={location.replace(' ', '+').replace(',', '%2C')}"
            f"&start={start}"
            f"&fromage=1"  # last 24 hours only
        )
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_=re.compile("job_seen_beacon"))

            for card in cards:
                try:
                    title_el = card.find("span", id=re.compile("jobTitle"))
                    company_el = card.find("span", {"data-testid": "company-name"})
                    loc_el = card.find("div", {"data-testid": "text-location"})
                    link_el = card.find("a", href=re.compile("/rc/clk|/pagead/clk"))
                    salary_el = card.find("div", {"data-testid": "attribute_snippet_testid"})
                    posted_el = card.find("span", {"data-testid": "myJobsStateDate"})

                    title = title_el.get_text(strip=True) if title_el else ""
                    company = company_el.get_text(strip=True) if company_el else ""
                    loc = loc_el.get_text(strip=True) if loc_el else location
                    salary = salary_el.get_text(strip=True) if salary_el else "Not disclosed"
                    posted = posted_el.get_text(strip=True) if posted_el else ""

                    jid = ""
                    if link_el:
                        href = link_el.get("href", "")
                        jid_match = re.search(r"jk=([a-z0-9]+)", href)
                        if jid_match:
                            jid = jid_match.group(1)

                    if not title or not company:
                        continue

                    job_url = f"https://in.indeed.com/viewjob?jk={jid}" if jid else ""
                    description = _fetch_indeed_jd(jid) if jid else ""

                    jobs.append({
                        "source": "indeed",
                        "job_id_external": f"indeed_{jid}" if jid else f"indeed_{title}_{company}",
                        "title": title,
                        "company": company,
                        "location": loc,
                        "job_url": job_url,
                        "experience_required": "",
                        "salary_range": salary,
                        "posted_date": posted,
                        "skills_required": [],
                        "description": description[:3000],
                    })
                except Exception:
                    continue
            time.sleep(1.5)
        except Exception as e:
            logger.warning(f"Indeed page start={start} error: {e}")

    return jobs


def _fetch_indeed_jd(job_id: str) -> str:
    try:
        url = f"https://in.indeed.com/viewjob?jk={job_id}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        jd_el = soup.find("div", id="jobDescriptionText")
        return jd_el.get_text(separator="\n", strip=True) if jd_el else ""
    except Exception:
        return ""


# ─────────────────────────── MAIN ──────────────────────────────

_INDIA_TERMS = {
    "bengaluru", "bangalore", "india", "mumbai", "delhi", "hyderabad",
    "pune", "chennai", "kolkata", "noida", "gurgaon", "gurugram",
    "ahmedabad", "jaipur", "kochi", "remote, india",
}

_FOREIGN_TERMS = {
    "united states", "usa", "u.s.", "canada", "united kingdom", "uk",
    "australia", "singapore", "germany", "netherlands", "france",
    "seattle", "bellevue", "mountain view", "san francisco", "new york",
    "boston", "chicago", "austin", "los angeles", "san jose", "sunnyvale",
    "palo alto", "cupertino", "toronto", "london", "sydney", "dubai",
    "remote, wa", "remote, ca", "remote, ny", "remote, tx",
}


def _is_india_job(job: dict) -> bool:
    loc = job.get("location", "").lower()
    if not loc:
        return True  # unknown — keep it
    # Immediately drop if a foreign term matches
    for term in _FOREIGN_TERMS:
        if term in loc:
            return False
    # Keep if any India term matches
    for term in _INDIA_TERMS:
        if term in loc:
            return True
    # Location present but no known India term — keep (could be "HSR Layout" etc.)
    return True


def scrape_all_jobs(keyword: str = "product manager", location: str = "Bengaluru") -> list[dict]:
    """Scrape PM jobs from Naukri + Indeed (last 24 hours, India only).
    LinkedIn removed — guest API returns US jobs and is too slow.
    """
    all_jobs = []
    logger.info("Scraping Naukri (last 24h)...")
    all_jobs += scrape_naukri(keyword, location.lower())
    logger.info(f"  Got {len(all_jobs)} Naukri jobs")

    logger.info("Scraping Indeed India (last 24h)...")
    in_jobs = scrape_indeed(keyword, location + ", Karnataka")
    all_jobs += in_jobs
    logger.info(f"  Got {len(in_jobs)} Indeed jobs")

    # Filter out US-located jobs
    before = len(all_jobs)
    all_jobs = [j for j in all_jobs if _is_india_job(j)]
    logger.info(f"  Dropped {before - len(all_jobs)} non-India jobs")

    # Deduplicate by external ID
    seen = set()
    unique = []
    for j in all_jobs:
        key = j["job_id_external"]
        if key not in seen:
            seen.add(key)
            unique.append(j)

    logger.info(f"Total unique jobs: {len(unique)}")
    return unique
