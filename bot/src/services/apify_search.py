"""
LinkedIn team search via Apify actors.

Supports two actor families (auto-detected from APIFY_ACTOR_ID):
  - People-search actors (e.g. M2FMdjRVeF1HPGFcc):
      use currentCompanies filter, maxItems ≤ 25, no searchQuery
  - Company-employee actors (e.g. arvestapi/linkedin-company-employees):
      use companyUrl (LinkedIn company page URL)

Returns member dicts ready for _merge_members (no LLM step needed).

Requires in .env:
  APIFY_TOKEN=apify_api_...
  APIFY_ACTOR_ID=M2FMdjRVeF1HPGFcc        # or arvestapi/linkedin-company-employees
  TEAM_SEARCH_MODE=apify
"""
import httpx
import structlog

from src.config import settings

log = structlog.get_logger()

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_TIMEOUT = 300.0  # LinkedIn scraping can take up to 5 minutes

# Actor IDs that use the company-employee URL-based input
_COMPANY_EMPLOYEE_ACTORS = {
    "arvestapi/linkedin-company-employees",
}


def _build_actor_input(company_name: str, linkedin_company_url: str, actor_id: str) -> dict:
    if actor_id in _COMPANY_EMPLOYEE_ACTORS:
        inp: dict = {"maxItems": 25}
        if linkedin_company_url:
            inp["companyUrl"] = linkedin_company_url
        else:
            inp["companyName"] = company_name
        return inp

    # People-search actors: currentCompanies filter, no searchQuery, maxItems ≤ 25
    return {
        "profileScraperMode": "Full",
        "currentCompanies": [company_name],
        "maxItems": 10,
        "startPage": 1,
    }


def _parse_apify_profile(item: dict, company_name: str) -> dict | None:
    """Convert a raw Apify LinkedIn profile item into a member dict for _build_member."""
    first = (item.get("firstName") or "").strip()
    last = (item.get("lastName") or "").strip()
    name = f"{first} {last}".strip()
    if not name:
        return None

    # Field is "linkedinUrl" (all lowercase) in this actor's output
    linkedin_url = item.get("linkedinUrl") or item.get("linkedInUrl") or item.get("profileUrl") or ""

    headline = item.get("headline") or ""

    # Location: city + country from parsed sub-object
    loc_parsed = (item.get("location") or {}).get("parsed") or {}
    loc_parts = [p for p in [loc_parsed.get("city"), loc_parsed.get("country")] if p]
    location = ", ".join(loc_parts)

    # Find current role at the target company from experience list
    role = ""
    experience_raw = item.get("experience") or []
    company_name_lower = company_name.lower()
    for exp in experience_raw:
        exp_company = (exp.get("companyName") or "").lower()
        end_text = ((exp.get("endDate") or {}).get("text") or "").lower()
        if company_name_lower in exp_company and end_text == "present":
            role = exp.get("position") or ""
            break

    # Collect past company names (ended roles only)
    prev_companies: list[str] = []
    seen: set[str] = set()
    for exp in experience_raw:
        exp_company = exp.get("companyName") or ""
        end_text = ((exp.get("endDate") or {}).get("text") or "").lower()
        if end_text != "present" and exp_company and exp_company.lower() not in seen:
            seen.add(exp_company.lower())
            prev_companies.append(exp_company)

    # Slim experience list: position + company + period + description (if non-empty)
    experience: list[dict] = []
    for exp in experience_raw:
        position = exp.get("position") or ""
        company = exp.get("companyName") or ""
        if not position and not company:
            continue
        start = (exp.get("startDate") or {}).get("text") or ""
        end = (exp.get("endDate") or {}).get("text") or ""
        period = f"{start} - {end}".strip(" -")
        entry: dict = {"position": position, "company": company}
        if period:
            entry["period"] = period
        desc = (exp.get("description") or "").strip()
        if desc:
            entry["description"] = desc
        experience.append(entry)

    # Slim education list: school + degree + field + period (if non-empty)
    education: list[dict] = []
    for edu in (item.get("education") or []):
        school = edu.get("schoolName") or ""
        if not school:
            continue
        entry: dict = {"school": school}
        degree = edu.get("degree") or ""
        field = edu.get("fieldOfStudy") or ""
        period = edu.get("period") or ""
        if degree:
            entry["degree"] = degree
        if field:
            entry["field"] = field
        if period:
            entry["period"] = period
        education.append(entry)

    # Top skills: names only, max 15
    top_skills = [s["name"] for s in (item.get("skills") or []) if s.get("name")][:15]

    # Photo: direct profile photo URL
    photo = item.get("photo") or ""

    return {
        "name": name,
        "role": role or headline,
        "linkedin_url": linkedin_url,
        "location": location,
        "bio": item.get("about") or "",
        "experience": experience,
        "education": education,
        "top_skills": top_skills,
        "photo": photo,
        "previous_companies": prev_companies,
        "profile_notes": headline,
    }


async def search_linkedin_team_apify(
    company_name: str,
    linkedin_company_url: str = "",
) -> list[dict]:
    """
    Run Apify actor and return member dicts ready for _merge_members.
    No LLM processing needed — data is parsed directly from structured profiles.
    """
    if not settings.APIFY_TOKEN:
        log.warning("apify.not_configured")
        return []

    actor_id = settings.APIFY_ACTOR_ID
    endpoint = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
    actor_input = _build_actor_input(company_name, linkedin_company_url, actor_id)

    log.info("apify.run_start", actor=actor_id, company=company_name, input=actor_input)
    try:
        async with httpx.AsyncClient(timeout=ACTOR_TIMEOUT) as client:
            resp = await client.post(
                endpoint,
                params={"token": settings.APIFY_TOKEN},
                json=actor_input,
            )
            resp.raise_for_status()
    except Exception as e:
        log.warning("apify.run_failed", error=str(e))
        return []

    items = resp.json()

    # Log pagination info if available
    if items:
        meta = (items[0].get("_meta") or {}).get("pagination") or {}
        if meta:
            log.info("apify.pagination", total=meta.get("totalElements"), pages=meta.get("totalPages"))

    members = []
    for item in items:
        m = _parse_apify_profile(item, company_name)
        if m:
            members.append(m)

    log.info("apify.linkedin_team_done", company=company_name, profiles_parsed=len(members))
    return members
