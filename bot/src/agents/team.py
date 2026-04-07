"""
Team agent: verifies project team members via public data.
"""
import structlog

log = structlog.get_logger()

TIER1_COMPANIES = frozenset({
    "google", "meta", "apple", "amazon", "microsoft", "netflix",
    "coinbase", "binance", "a16z", "andreessen horowitz",
    "polychain", "paradigm", "sequoia", "jump", "delphi",
    "ethereum foundation", "solana foundation", "consensys",
    "circle", "ripple", "chainalysis", "opensea",
})


async def team_node(state: dict) -> dict:
    """
    Verifies team by finding the team/about page and checking public data.
    Writes results to state['team_data'].

    Note: Does NOT scrape LinkedIn directly (violates ToS).
    Uses only publicly accessible page content and Google-indexed data.
    """
    project_name = state.get("project_name", "")
    project_urls = state.get("project_urls", {})
    log.info("team.start", project=project_name)

    team_data: dict = {"members": [], "flags": []}
    errors = list(state.get("errors", []))

    try:
        from src.services.scraper import DocumentationScraper
        from src.services.llm import LLMService

        scraper = DocumentationScraper()
        llm = LLMService()

        website = project_urls.get("website")
        team_page_url: str | None = None
        team_content = ""

        if website:
            team_page_url = await scraper.find_team_page(website)

        if team_page_url:
            page = await scraper.scrape_page(team_page_url)
            if page and page.text_content:
                team_content = page.text_content[:20_000]

        if team_content:
            members_raw = await llm.extract_team_members(team_content)

            verified_members = []
            flags: list[dict] = []

            for member in members_raw:
                name = member.get("name", "").strip()
                if not name:
                    continue

                linkedin = member.get("linkedin_url") or None
                prev_companies_raw = member.get("previous_companies", []) or []
                prev_companies = [c.lower() for c in prev_companies_raw]

                verified = bool(linkedin)
                has_tier1 = any(
                    tier1 in " ".join(prev_companies)
                    for tier1 in TIER1_COMPANIES
                )

                member_flags: list[str] = []
                if not linkedin:
                    member_flags.append("No LinkedIn profile found")

                verified_members.append({
                    "name": name,
                    "role": member.get("role", ""),
                    "linkedin_url": linkedin,
                    "verified": verified,
                    "previous_companies": prev_companies_raw,
                    "has_tier1_background": has_tier1,
                    "red_flags": member_flags,
                    "profile_notes": member.get("profile_notes", ""),
                })

            # Team-level risk flags
            total = len(verified_members)
            if total == 0:
                flags.append({
                    "type": "red",
                    "message": "No team members found on the website",
                })
            else:
                anon_count = sum(1 for m in verified_members if not m["verified"])
                tier1_count = sum(1 for m in verified_members if m["has_tier1_background"])

                if anon_count == total:
                    flags.append({
                        "type": "red",
                        "message": "Fully anonymous team — no LinkedIn profiles found",
                    })
                elif anon_count > total // 2:
                    flags.append({
                        "type": "yellow",
                        "message": f"{anon_count}/{total} team members have no verified LinkedIn profile",
                    })

                if tier1_count > 0:
                    flags.append({
                        "type": "green",
                        "message": f"{tier1_count} member(s) with Tier-1 company background",
                    })

            team_data = {
                "members": verified_members,
                "flags": flags,
                "team_page_url": team_page_url,
            }
        else:
            log.info("team.no_content", project=project_name, website=website)
            team_data = {
                "members": [],
                "flags": [{"type": "yellow", "message": "Team page not found or not accessible"}],
                "team_page_url": None,
            }

    except Exception as e:
        log.warning("team.failed", error=str(e))
        errors.append(f"Team: {e}")

    log.info(
        "team.done",
        project=project_name,
        member_count=len(team_data.get("members", [])),
    )

    return {
        **state,
        "team_data": team_data,
        "team_done": True,
        "errors": errors,
    }
