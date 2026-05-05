"""
Team agent: finds and verifies project team members via public web search.

Strategy:
1. Search DuckDuckGo for LinkedIn profiles of senior people at the project
   (Founders, C-Suite, Heads, technical leads, etc.)
2. Also scrape the LinkedIn company page if the URL is known
3. Merge all sources, deduplicate by name, apply risk flags
"""
import asyncio
import structlog

log = structlog.get_logger()

TIER1_COMPANIES = frozenset({
    "google", "meta", "apple", "amazon", "microsoft", "netflix",
    "coinbase", "binance", "a16z", "andreessen horowitz",
    "polychain", "paradigm", "sequoia", "jump", "delphi",
    "ethereum foundation", "solana foundation", "consensys",
    "circle", "ripple", "chainalysis", "opensea",
})


_STEPS: dict[str, dict[str, str]] = {
    "resolve_urls":       {"ru": "Ищем сайт проекта...",                              "en": "Searching project website..."},
    "resolve_company":    {"ru": "Определяем точное название компании в LinkedIn...",  "en": "Resolving exact LinkedIn company name..."},
    "company_found":      {"ru": "Компания на LinkedIn: {name}",                       "en": "LinkedIn company: {name}"},
    "apify_search":       {"ru": "Запрашиваем профили через Apify...",                 "en": "Fetching profiles via Apify..."},
    "search_members":     {"ru": "Ищем участников команды...",                         "en": "Searching team members..."},
    "search_found":       {"ru": "Найдено {n} LinkedIn профилей, анализируем...",      "en": "Found {n} LinkedIn profiles, analysing..."},
    "linkedin_page":      {"ru": "Анализируем LinkedIn страницу проекта...",           "en": "Analysing project LinkedIn page..."},
    "find_team_page":     {"ru": "Ищем страницу команды на сайте...",                  "en": "Looking for team page on website..."},
    "read_team_page":     {"ru": "Читаем страницу команды...",                         "en": "Reading team page..."},
}


def _step(key: str, lang: str, **kwargs) -> str:
    text = _STEPS[key].get(lang) or _STEPS[key]["ru"]
    return text.format(**kwargs) if kwargs else text


_FLAGS: dict[str, dict[str, str]] = {
    "no_members":      {"ru": "Участники команды не найдены",                             "en": "No team members found"},
    "fully_anon":      {"ru": "Полностью анонимная команда — профили LinkedIn не найдены", "en": "Fully anonymous team — no LinkedIn profiles found"},
    "no_linkedin":     {"ru": "Нет LinkedIn профиля",                                     "en": "No LinkedIn profile found"},
}


def _flag_msg(key: str, lang: str, **kwargs) -> str:
    text = _FLAGS[key].get(lang) or _FLAGS[key]["ru"]
    return text.format(**kwargs) if kwargs else text


def _build_member(raw: dict, source: str, lang: str = "ru") -> dict | None:
    name = raw.get("name", "").strip()
    if not name:
        return None
    linkedin = raw.get("linkedin_url") or None
    prev_raw = raw.get("previous_companies", []) or []
    prev_lower = [c.lower() for c in prev_raw]
    has_tier1 = any(tier1 in " ".join(prev_lower) for tier1 in TIER1_COMPANIES)
    member_flags = [] if linkedin else [_flag_msg("no_linkedin", lang)]
    return {
        "name": name,
        "role": raw.get("role") or "",
        "linkedin_url": linkedin,
        "verified": bool(linkedin),
        "location": raw.get("location") or "",
        "bio": raw.get("bio") or "",
        "experience": raw.get("experience") or [],
        "education": raw.get("education") or [],
        "top_skills": raw.get("top_skills") or [],
        "photo": raw.get("photo") or "",
        "previous_companies": prev_raw,
        "has_tier1_background": has_tier1,
        "red_flags": member_flags,
        "profile_notes": raw.get("profile_notes") or "",
        "source": source,
    }


def _merge_members(base: list[dict], additions: list[dict], source: str, lang: str = "ru") -> list[dict]:
    """Append members from additions that aren't already in base (by name)."""
    existing = {m["name"].lower() for m in base}
    result = list(base)
    for raw in additions:
        m = _build_member(raw, source, lang=lang)
        if m and m["name"].lower() not in existing:
            existing.add(m["name"].lower())
            result.append(m)
    return result


def _build_flags(members: list[dict], lang: str = "ru") -> list[dict]:
    flags: list[dict] = []
    total = len(members)
    if total == 0:
        flags.append({"type": "red", "message": _flag_msg("no_members", lang)})
        return flags

    anon_count = sum(1 for m in members if not m["verified"])
    tier1_count = sum(1 for m in members if m["has_tier1_background"])

    if anon_count == total:
        flags.append({"type": "red", "message": _flag_msg("fully_anon", lang)})
    elif anon_count > total // 2:
        if lang == "ru":
            msg = f"{anon_count}/{total} участников команды не имеют подтверждённого профиля LinkedIn"
        else:
            msg = f"{anon_count}/{total} team members have no verified LinkedIn profile"
        flags.append({"type": "yellow", "message": msg})

    if tier1_count > 0:
        if lang == "ru":
            msg = f"{tier1_count} участник(ов) с опытом в компаниях Tier-1"
        else:
            msg = f"{tier1_count} member(s) with Tier-1 company background"
        flags.append({"type": "green", "message": msg})

    return flags


async def team_node(state: dict) -> dict:
    project_name = state.get("project_name", "")
    project_urls = state.get("project_urls", {})
    lang = state.get("lang", "ru")
    log.info("team.start", project=project_name)

    from src.agents.graph import push_step

    team_data: dict = {"members": [], "flags": []}
    errors = list(state.get("errors", []))

    if not project_urls.get("website") and not project_urls.get("twitter"):
        await push_step("team", _step("resolve_urls", lang))
        from src.agents.resolve_urls import resolve_project_urls
        project_urls = await resolve_project_urls(project_name, project_urls)

    try:
        from src.services.scraper import DocumentationScraper
        from src.services.llm import LLMService
        from src.services.search import search_linkedin_team, resolve_linkedin_company_name
        from src.config import settings

        scraper = DocumentationScraper()
        llm = LLMService()

        # ── 1. Resolve exact LinkedIn company name ────────────────────
        await push_step("team", _step("resolve_company", lang))
        linkedin_company_url = project_urls.get("linkedin", "")
        company_name = await resolve_linkedin_company_name(project_name, linkedin_company_url)
        if company_name != project_name:
            await push_step("team", _step("company_found", lang, name=company_name))
        log.info("team.company_name", project=project_name, linkedin_name=company_name)

        # ── 2. Search LinkedIn profiles ───────────────────────────────
        mode = settings.TEAM_SEARCH_MODE
        members: list[dict] = []

        if mode == "apify":
            from src.services.apify_search import search_linkedin_team_apify
            await push_step("team", _step("apify_search", lang))
            apify_members = await search_linkedin_team_apify(company_name, linkedin_company_url)
            members = _merge_members(members, apify_members, source="apify", lang=lang)
            log.info("team.apify_done", project=project_name, count=len(members))
        else:
            await push_step("team", _step("search_members", lang))
            search_results = await search_linkedin_team(company_name)
            log.info("team.search_done", project=project_name, mode=mode, results=len(search_results))
            if search_results:
                await push_step("team", _step("search_found", lang, n=len(search_results)))
                search_members_raw = await llm.extract_team_from_search_results(
                    search_results, project_name, lang=lang
                )
                members = _merge_members(members, search_members_raw, source="web_search", lang=lang)
                log.info("team.search_members_extracted", project=project_name, count=len(members))

        # ── 3. LinkedIn company page (brave mode only) ────────────────
        linkedin_meta: dict = {}
        if mode != "apify" and linkedin_company_url:
            await push_step("team", _step("linkedin_page", lang))
            linkedin_page = await scraper.scrape_page(linkedin_company_url)
            if linkedin_page and linkedin_page.text_content:
                linkedin_meta = await llm.extract_linkedin_company_data(
                    linkedin_page.text_content[:20_000], lang=lang
                )
                members = _merge_members(
                    members, linkedin_meta.get("members", []), source="linkedin_company", lang=lang
                )
                log.info(
                    "team.linkedin_scraped",
                    project=project_name,
                    employees=linkedin_meta.get("employee_count_range"),
                    new_members=len(linkedin_meta.get("members", [])),
                )

        # ── 4. Website team page (fallback) ──────────────────────────
        website = project_urls.get("website")
        team_page_url: str | None = None
        if website and not members:
            await push_step("team", _step("find_team_page", lang))
            team_page_url = await scraper.find_team_page(website)
            if team_page_url:
                await push_step("team", _step("read_team_page", lang))
                page = await scraper.scrape_page(team_page_url)
                if page and page.text_content:
                    site_members_raw = await llm.extract_team_members(page.text_content[:20_000], lang=lang)
                    members = _merge_members(members, site_members_raw, source="website", lang=lang)

        team_data = {
            "members": members,
            "flags": _build_flags(members, lang=lang),
            "team_page_url": team_page_url,
            "linkedin_url": linkedin_company_url,
            "linkedin_employee_count_range": linkedin_meta.get("employee_count_range"),
            "linkedin_company_description": linkedin_meta.get("company_description"),
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
        "project_urls": project_urls,
        "errors": errors,
    }


if __name__ == "__main__":
    import json
    import logging
    import sys
    import types
    from pathlib import Path

    # Ensure 'src' package is importable when running as a script
    sys.path.insert(0, str(Path(__file__).parents[2]))

    # Load .env
    try:
        from dotenv import load_dotenv
        for _env in [Path(__file__).parents[3] / ".env", Path(__file__).parents[4] / ".env"]:
            if _env.exists():
                load_dotenv(_env)
                print(f"[team] Loaded .env from {_env}")
                break
    except ImportError:
        pass

    # Stub cache module
    async def _cache_get(key: str):
        return None
    async def _cache_set(key: str, value, ttl: int):
        pass
    async def _cache_incr(key: str, ttl_if_new: int) -> int:
        return 0
    _fake_cache = types.ModuleType("src.services.cache")
    _fake_cache.cache_get = _cache_get
    _fake_cache.cache_set = _cache_set
    _fake_cache.cache_incr = _cache_incr
    sys.modules["src.services.cache"] = _fake_cache

    # Stub push_step
    async def _push_step_stub(agent_name: str, step_text: str) -> None:
        print(f"  [{agent_name}] {step_text}")
    _fake_graph = types.ModuleType("src.agents.graph")
    _fake_graph.push_step = _push_step_stub
    sys.modules["src.agents.graph"] = _fake_graph

    # Configure structlog → console
    import structlog as _structlog
    _structlog.configure(
        processors=[_structlog.stdlib.add_log_level, _structlog.dev.ConsoleRenderer(colors=True)],
        wrapper_class=_structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=_structlog.PrintLoggerFactory(),
    )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", stream=sys.stdout)

    # Parse CLI args: <project_name> [--linkedin URL] [--website URL] [--lang ru|en]
    _argv = sys.argv[1:]
    if not _argv or _argv[0].startswith("-"):
        print("Usage: python team.py <project_name> [--linkedin URL] [--website URL] [--lang ru|en]")
        sys.exit(1)

    _project = _argv[0]
    _linkedin = ""
    _website = ""
    _lang = "ru"
    _i = 1
    while _i < len(_argv):
        if _argv[_i] == "--linkedin" and _i + 1 < len(_argv):
            _linkedin = _argv[_i + 1]; _i += 2
        elif _argv[_i] == "--website" and _i + 1 < len(_argv):
            _website = _argv[_i + 1]; _i += 2
        elif _argv[_i] == "--lang" and _i + 1 < len(_argv):
            _lang = _argv[_i + 1]; _i += 2
        else:
            _i += 1

    from src.config import settings as _settings
    print(f"TEAM_SEARCH_MODE = {_settings.TEAM_SEARCH_MODE}")
    print(f"APIFY_ACTOR_ID   = {_settings.APIFY_ACTOR_ID}")
    print(f"APIFY_TOKEN      = {'SET' if _settings.APIFY_TOKEN else 'NOT SET'}")
    print(f"{'='*60}\nProject: {_project}\n{'='*60}\n")

    _state = {
        "project_name": _project,
        "project_query": _project,
        "project_urls": {k: v for k, v in [("linkedin", _linkedin), ("website", _website)] if v},
        "lang": _lang,
        "enabled_modules": ["team"],
        "errors": [],
    }

    async def _run() -> None:
        result = await team_node(_state)
        team_data = result.get("team_data", {})
        errors = result.get("errors", [])
        print(f"\n{'='*60}\nTEAM DATA:\n{'='*60}")
        print(json.dumps(team_data, indent=2, ensure_ascii=False, default=str))
        if errors:
            print(f"\nERRORS:")
            for e in errors:
                print(f"  - {e}")

    asyncio.run(_run())
