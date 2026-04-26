"""
Analyst node: computes final score, generates report, saves to DB.
"""
import structlog

log = structlog.get_logger()

_TIER1_FUNDS = {"a16z", "paradigm", "sequoia", "binance labs", "coinbase ventures",
                "polychain", "multicoin", "pantera", "framework", "dragonfly"}

ANALYST_PROMPT = """You are a professional crypto analyst. Based on the collected data, evaluate the project {project_name}.

Aggregator data: {aggregator_data}
Documentation data: {documentation_data}
Social metrics: {social_data}
Team verification: {team_data}
Cross-check results: {cross_check_results}

Respond ONLY in valid JSON (no markdown fences):
{{
  "overall_score": <integer 0-100>,
  "recommendation": "<DYOR|Interesting|Strong|Avoid>",
  "summary": "<3-4 sentence overview in Russian>",
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "weaknesses": ["<weakness 1>", "<weakness 2>", ...],
  "tokenomics_score": <0-25>,
  "investors_score": <0-25>,
  "team_score": <0-25>,
  "social_score": <0-25>
}}
"""


def _build_tokenomics(documentation_data: dict, cr_vesting) -> dict:
    """
    Merge documentation tokenomics with CryptoRank vesting data.
    CryptoRank vesting takes priority for vesting_schedules if available.
    cr_vesting may be a dict {"tge_start_date": ..., "allocations": [...]}
    or a legacy list for backwards compatibility.
    """
    base = dict(documentation_data) if documentation_data else {}
    if isinstance(cr_vesting, dict):
        allocations = cr_vesting.get("allocations", [])
        if allocations:
            base["vesting_schedules"] = allocations
        tge_start = cr_vesting.get("tge_start_date")
        if tge_start:
            base["tge_start_date"] = tge_start
    elif isinstance(cr_vesting, list) and cr_vesting:
        base["vesting_schedules"] = cr_vesting
    if "vesting_schedules" not in base:
        base["vesting_schedules"] = []
    # Derive token_distribution from vesting schedules if not already set
    if not base.get("token_distribution"):
        base["token_distribution"] = {
            s["recipient_type"]: s["total_percent"]
            for s in base["vesting_schedules"]
            if s.get("recipient_type") and s.get("total_percent")
        }
    return base


def _build_funding_rounds(funding_rounds: list) -> list[dict]:
    """
    Convert CryptoRank funding round format to mini-app FundingRound format.
    CryptoRank: {round_type, date, amount_usd, valuation_usd, investors, announcement, ...}
    Mini-app:   {round_name, date, amount_usd, valuation_usd, investors, announcement}
    """
    result = []
    for r in funding_rounds or []:
        result.append({
            "round_name": r.get("round_type", "Unknown"),
            "date": r.get("date"),
            "amount_usd": r.get("amount_usd"),
            "valuation_usd": r.get("valuation_usd"),
            "investors": r.get("investors", []),
            "announcement": r.get("announcement"),
        })
    return result


def _build_investor_list(investors_list: list, funding_rounds: list) -> list[dict]:
    """
    Build deduplicated investor list.
    Prefers investors_list (has logos + tiers) from /investors-list endpoint;
    falls back to extracting from funding_rounds if investors_list is empty.
    """
    if investors_list:
        return [
            {
                "name": inv.get("name", ""),
                "logo": inv.get("logo"),
                "tier": str(inv["tier"]) if inv.get("tier") is not None else None,
                "round": (inv.get("stage") or [""])[0],
                "stages": inv.get("stage") or [],
                "category": inv.get("category"),
                "is_lead": inv.get("is_lead", False),
                "portfolio_notable": [],
            }
            for inv in investors_list
            if inv.get("name")
        ]
    # fallback: extract from per-round investor lists
    seen: dict[str, dict] = {}
    for r in funding_rounds or []:
        round_type = r.get("round_type", "")
        for inv in r.get("investors", []):
            if isinstance(inv, str):
                name, logo = inv, None
            elif isinstance(inv, dict):
                name, logo = inv.get("name", ""), inv.get("logo")
            else:
                continue
            if name and name not in seen:
                seen[name] = {"name": name, "logo": logo, "round": round_type, "portfolio_notable": []}
    return list(seen.values())


def _calculate_score(
    aggregator_data: dict,
    documentation_data: dict,
    social_data: dict,
    team_data: dict,
    cross_check_results: list,
    prev_sub_scores: dict | None = None,
    enabled_modules: list | None = None,
) -> tuple[int, dict]:
    """Calculate overall score based on sub-scores and penalties.

    If prev_sub_scores is provided and a module is not in enabled_modules,
    the previous score for that section is reused instead of recalculating.
    """
    if prev_sub_scores is None:
        prev_sub_scores = {}
    if enabled_modules is None:
        enabled_modules = ["aggregator", "documentation", "social", "team"]

    scores = {
        "tokenomics": prev_sub_scores.get("tokenomics", 12),
        "investors": prev_sub_scores.get("investors", 12),
        "team": prev_sub_scores.get("team", 12),
        "social": prev_sub_scores.get("social", 12),
    }

    if "aggregator" in enabled_modules:
        # Tokenomics scoring (0-25)
        # coingecko has flat structure: fdv_usd, market_cap_usd, current_price_usd
        coingecko = aggregator_data.get("coingecko", {}) or {}
        fdv = coingecko.get("fdv_usd") or 0
        mcap = coingecko.get("market_cap_usd") or 0

        if fdv and mcap:
            ratio = fdv / mcap if mcap else 10
            if ratio < 3:
                scores["tokenomics"] = 22
            elif ratio < 5:
                scores["tokenomics"] = 18
            elif ratio < 10:
                scores["tokenomics"] = 12
            else:
                scores["tokenomics"] = 6

        # Investors scoring (0-25)
        funding_rounds = (aggregator_data.get("cryptorank", {}) or {}).get("funding_rounds", []) or []
        tier1_count = 0
        for round_data in funding_rounds:
            if isinstance(round_data, dict):
                for inv in round_data.get("investors", []):
                    inv_name = inv if isinstance(inv, str) else inv.get("name", "")
                    if any(t in inv_name.lower() for t in _TIER1_FUNDS):
                        tier1_count += 1
        scores["investors"] = min(25, 10 + tier1_count * 5)

    if "team" in enabled_modules:
        # Team scoring (0-25)
        members = team_data.get("members", []) or []
        if members:
            verified = sum(1 for m in members if m.get("verified"))
            tier1_bg = sum(1 for m in members if m.get("has_tier1_background"))
            total = len(members)
            scores["team"] = min(25, int(10 + (verified / total) * 10 + tier1_bg * 2))
        else:
            scores["team"] = 5

    if "social" in enabled_modules:
        # Social scoring (0-25)
        followers = social_data.get("followers_count", 0) or 0
        engagement = social_data.get("engagement_rate", 0) or 0
        sentiment = float(social_data.get("sentiment_score", 0.0) or 0.0)
        kol_count = len(social_data.get("kol_mentions", []) or [])
        if followers > 100_000 and engagement > 0.01:
            scores["social"] = 22
        elif followers > 50_000:
            scores["social"] = 16
        elif followers > 10_000:
            scores["social"] = 12
        else:
            scores["social"] = 6
        scores["social"] = min(25, scores["social"] + int(sentiment * 3) + min(kol_count, 3))

    # Penalties
    penalty = 0
    for flag in cross_check_results:
        if flag.get("type") == "red":
            penalty += 5
        elif flag.get("type") == "yellow":
            penalty += 2

    base_score = sum(scores.values())
    overall = max(0, min(100, base_score - penalty))

    return overall, scores


async def _load_prev_report(project_slug: str, user_id: int) -> dict:
    """Load the latest completed report for this project+user from DB."""
    try:
        from src.db.engine import async_session_factory
        from src.db.repositories import ProjectRepository, ReportRepository
        async with async_session_factory() as session:
            proj_repo = ProjectRepository(session)
            project = await proj_repo.get_by_slug(project_slug)
            if project is None:
                log.info("analyst.prev_report_not_found", reason="project_not_in_db", slug=project_slug)
                return {}
            report_repo = ReportRepository(session)
            prev = await report_repo.get_latest_by_project(user_id=user_id, project_id=project.id)
            if prev and prev.report_data:
                log.info("analyst.prev_report_loaded", report_id=prev.id, slug=project_slug)
                return dict(prev.report_data)
            log.info("analyst.prev_report_not_found", reason="no_completed_report", slug=project_slug, user_id=user_id)
    except Exception as e:
        import traceback
        log.warning("analyst.prev_report_load_failed", error=str(e), trace=traceback.format_exc())
    return {}


async def analyst_node(state: dict) -> dict:
    """
    Generates the final analysis report with scoring.
    Merges new data with the previous report (if any) so that
    partial-mode analyses (market/social/team/docs) enrich the report
    instead of overwriting it.
    Saves to PostgreSQL.
    """
    project_name = state.get("project_name", "")
    project_slug = state.get("project_slug", "")
    enabled_modules: list[str] = state.get("enabled_modules", ["aggregator", "documentation", "social", "team"])
    log.info("analyst.start", project=project_name, modules=enabled_modules)

    from src.agents.graph import push_forming_report
    await push_forming_report()

    aggregator_data = state.get("aggregator_data", {}) or {}
    documentation_data = state.get("documentation_data", {}) or {}
    social_data = state.get("social_data", {}) or {}
    team_data = state.get("team_data", {}) or {}
    cross_check_results = list(state.get("cross_check_results", []))
    if state.get("cr_limit_reached"):
        cross_check_results.append({
            "type": "yellow",
            "category": "Data",
            "message": "Дневной лимит CryptoRank исчерпан — данные по инвесторам/раундам могут быть неполными",
        })
    errors = list(state.get("errors", []))
    coingecko = aggregator_data.get("coingecko", {}) or {}
    cr = (aggregator_data.get("cryptorank", {}) or {})

    # ── Load previous report and extract its sub-scores ──────────────────────
    prev_report = await _load_prev_report(project_slug, state.get("user_id", 0))
    prev_scorecard = prev_report.get("scorecard", {}) or {}
    prev_sub_scores = {
        "tokenomics": prev_scorecard.get("tokenomics_score", 12),
        "investors": prev_scorecard.get("investors_score", 12),
        "team": prev_scorecard.get("team_score", 12),
        "social": prev_scorecard.get("social_score", 12),
    }

    # ── Build effective data for LLM: use prev sections when not re-run ──────
    # This gives the LLM full context even in partial-mode runs.
    eff_social = social_data if "social" in enabled_modules else (prev_report.get("social") or {})
    eff_team = team_data if "team" in enabled_modules else {"members": prev_report.get("team") or []}
    # For aggregator/docs we pass the current data; LLM will see prev tokenomics via social/team anyway.

    try:
        from src.services.llm import LLMService
        llm = LLMService()

        llm_result = await llm.generate_final_report(
            project_name=project_name,
            aggregator_data=aggregator_data,
            documentation_data=documentation_data,
            social_data=eff_social,
            team_data=eff_team,
            cross_check_results=cross_check_results,
            lang=state.get("lang", "ru"),
        )

        overall_score, sub_scores = _calculate_score(
            aggregator_data, documentation_data, eff_social, eff_team, cross_check_results,
            prev_sub_scores=prev_sub_scores,
            enabled_modules=enabled_modules,
        )

        # Override with LLM score if provided — blend: 70% formula, 30% LLM
        if llm_result.get("overall_score"):
            overall_score = int(overall_score * 0.7 + llm_result["overall_score"] * 0.3)

        recommendation = llm_result.get("recommendation", "DYOR")

        # ── Build new data sources (merge with previous) ──────────────────────
        new_sources: list[str] = []
        if cr:
            new_sources.append("Cryptorank")
        # CoinGecko: fetched by aggregator OR independently by social node
        if coingecko or eff_social.get("coingecko_summary"):
            new_sources.append("CoinGecko")
        if documentation_data.get("docs_url"):
            new_sources.append("Project Documentation")
        elif documentation_data.get("scraped_from_website"):
            new_sources.append("Project Website")
        if eff_social.get("handle"):
            new_sources.append("Twitter/X")
        # Team: add source when team page was found, even if members list is empty
        if eff_team.get("members") or eff_team.get("team_page_url"):
            new_sources.append("Project Website")
        # Preserve sources from previous report
        prev_sources = prev_report.get("data_sources") or []
        data_sources = list(dict.fromkeys(prev_sources + new_sources))  # dedup, preserve order

        # ── Start from previous report, then overwrite updated sections ──────
        report: dict = {**prev_report} if prev_report else {}

        # Build project_links from all known URLs (merge prev + current, current wins)
        project_urls = state.get("project_urls", {})
        prev_links = prev_report.get("project_links", {}) or {}
        project_links: dict = {**prev_links}
        # Copy ALL URL types (website, twitter, gitbook, whitepaper, etc.)
        for key, url in project_urls.items():
            if url:
                project_links[key] = url
        # Docs URL from documentation agent (single canonical link in socials)
        if documentation_data.get("docs_url") and not project_links.get("docs"):
            project_links["docs"] = documentation_data["docs_url"]
        # Always include CryptoRank page
        if project_slug and not project_links.get("cryptorank"):
            project_links["cryptorank"] = f"https://cryptorank.io/price/{project_slug}"

        # Always update identity and scoring fields
        report.update({
            "project_name": project_name,
            "project_slug": project_slug,
            "overall_score": overall_score,
            "recommendation": recommendation,
            "scorecard": {
                "tokenomics_score": sub_scores["tokenomics"],
                "investors_score": sub_scores["investors"],
                "team_score": sub_scores["team"],
                "social_score": sub_scores["social"],
                "overall_score": overall_score,
            },
            "risk_flags": cross_check_results,
            "strengths": llm_result.get("strengths") or prev_report.get("strengths", []),
            "weaknesses": llm_result.get("weaknesses") or prev_report.get("weaknesses", []),
            "summary": llm_result.get("summary") or prev_report.get("summary", ""),
            "data_sources": data_sources,
            "project_links": project_links,
        })

        # Overwrite aggregator-derived sections only when aggregator was run
        if "aggregator" in enabled_modules:
            report["coingecko_summary"] = {
                "fdv_usd": coingecko.get("fdv_usd"),
                "market_cap_usd": coingecko.get("market_cap_usd"),
            }
            report["funding_rounds"] = _build_funding_rounds(cr.get("funding_rounds", []))
            report["investors"] = _build_investor_list(
                cr.get("investors_list", []),
                cr.get("funding_rounds", []),
            )

        # If aggregator didn't run, try to use CoinGecko data fetched by social node
        if "coingecko_summary" not in report:
            cg_from_social = social_data.get("coingecko_summary") or {}
            report["coingecko_summary"] = {
                "fdv_usd": cg_from_social.get("fdv_usd"),
                "market_cap_usd": cg_from_social.get("market_cap_usd"),
            }

        # Overwrite tokenomics when aggregator or documentation was run
        if "aggregator" in enabled_modules or "documentation" in enabled_modules:
            report["tokenomics"] = _build_tokenomics(
                documentation_data,
                cr.get("vesting") or {},
            )
            cr_project = cr.get("project", {}) or {}
            tok = report["tokenomics"]
            if not tok.get("token_symbol") and cr_project.get("symbol"):
                tok["token_symbol"] = cr_project["symbol"]
            if not tok.get("max_supply") and cr_project.get("max_supply"):
                tok["max_supply"] = cr_project["max_supply"]
            elif not tok.get("max_supply") and cr_project.get("total_supply"):
                tok["max_supply"] = cr_project["total_supply"]

        # Overwrite documentation section only when documentation was run
        if "documentation" in enabled_modules:
            report["documentation"] = {
                "project_description": documentation_data.get("project_description"),
                "key_features": documentation_data.get("key_features", []),
                "token_name": documentation_data.get("token_name"),
                "token_symbol": documentation_data.get("token_symbol"),
                "total_supply": documentation_data.get("total_supply"),
                "unusual_conditions": documentation_data.get("unusual_conditions", []),
                "data_completeness": documentation_data.get("data_completeness"),
                "docs_url": documentation_data.get("docs_url"),
                "scraped_pages": documentation_data.get("scraped_pages", []),
                "project_links": documentation_data.get("project_links", {}),
                "scraped_from_website": documentation_data.get("scraped_from_website", False),
                "website_url": documentation_data.get("website_url"),
                "error": documentation_data.get("error"),
            }

        # Overwrite social section only when social was run
        if "social" in enabled_modules:
            report["social"] = social_data

        # Overwrite team section only when team was run
        if "team" in enabled_modules:
            report["team"] = team_data.get("members", [])

        # ── Save to DB ────────────────────────────────────────────────────────
        try:
            from src.db.engine import async_session_factory
            from src.db.repositories import ProjectRepository, ReportRepository
            async with async_session_factory() as session:
                proj_repo = ProjectRepository(session)
                report_repo = ReportRepository(session)

                project, _ = await proj_repo.get_or_create(
                    name=project_name,
                    slug=project_slug,
                    website_url=state.get("project_urls", {}).get("website"),
                    twitter_url=state.get("project_urls", {}).get("twitter"),
                    docs_url=state.get("project_urls", {}).get("docs"),
                )

                db_report = await report_repo.create(
                    project_id=project.id,
                    user_id=state.get("user_id", 0),
                )
                await report_repo.complete(
                    report_id=db_report.id,
                    report_data=report,
                    overall_score=overall_score,
                    recommendation=recommendation,
                    risk_flags=cross_check_results,
                    errors=errors,
                )
                await session.commit()
                report["id"] = db_report.id
        except Exception as e:
            import traceback
            log.error("analyst.db_save_failed", error=str(e), trace=traceback.format_exc())

        log.info("analyst.done", project=project_name, score=overall_score, recommendation=recommendation)

        return {
            **state,
            "report": report,
            "status": "completed",
            "errors": errors,
        }

    except Exception as e:
        log.error("analyst.failed", project=project_name, error=str(e))
        errors.append(f"Analyst: {e}")
        return {
            **state,
            "status": "failed",
            "errors": errors,
        }
