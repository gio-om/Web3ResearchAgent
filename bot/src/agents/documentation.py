"""
Documentation agent: scrapes and analyzes project documentation via Claude.
"""
import structlog

log = structlog.get_logger()

DOCUMENTATION_PROMPT = """You are a crypto analyst. Read the project documentation below and extract the most important and interesting information about the project.
{lang_instruction}
Return ONLY valid JSON, no markdown fences, no extra text.

{{
  "project_description": "<2-3 sentence summary of what the project does>",
  "key_features": ["<feature 1>", "<feature 2>", ...],
  "token_name": "<string or null>",
  "token_symbol": "<string or null>",
  "total_supply": <number or null>,
  "unusual_conditions": ["<anything risky, unusual or suspicious found in the docs>"],
  "data_completeness": "<high|medium|low — how complete and detailed the documentation is>"
}}

Documentation text:
{text}
"""

WEBSITE_PROMPT = """You are a crypto analyst. The text below was collected from the project's main website (official documentation was not found). Extract as much relevant project information as possible.
{lang_instruction}
Return ONLY valid JSON, no markdown fences, no extra text.

{{
  "project_description": "<2-3 sentence summary of what the project does>",
  "key_features": ["<feature 1>", "<feature 2>", ...],
  "token_name": "<string or null>",
  "token_symbol": "<string or null>",
  "total_supply": <number or null>,
  "unusual_conditions": ["<anything risky, unusual or suspicious found>"],
  "data_completeness": "<high|medium|low — how complete and detailed the collected information is>"
}}

Website content:
{text}
"""

def _lang_instruction(lang: str) -> str:
    return (
        "Write project_description, key_features, and unusual_conditions in Russian."
        if lang == "ru" else
        "Write project_description, key_features, and unusual_conditions in English."
    )

_STEPS: dict[str, dict[str, str]] = {
    "search_links":      {"ru": "Ищем ссылки проекта...",                       "en": "Searching project links..."},
    "search_docs":       {"ru": "Ищем страницу документации...",                "en": "Searching docs page..."},
    "found_docs":        {"ru": "Найдена документация: {url}",                  "en": "Found documentation: {url}"},
    "reading_page":      {"ru": "Читаем: {url}",                                "en": "Reading: {url}"},
    "analysing":         {"ru": "Анализируем документацию ({n} стр.) с AI...", "en": "Analysing documentation ({n} pages) with AI..."},
    "fallback_website":  {"ru": "Документация не найдена, читаем сайт...",      "en": "Docs not found, reading website..."},
    "analysing_website": {"ru": "Анализируем сайт ({n} стр.) с AI...",         "en": "Analysing website ({n} pages) with AI..."},
}


def _step(key: str, lang: str, **kwargs) -> str:
    text = _STEPS[key].get(lang) or _STEPS[key]["ru"]
    return text.format(**kwargs) if kwargs else text


async def documentation_node(state: dict) -> dict:
    """
    Discovers, scrapes, and analyzes project documentation using LLM.
    Falls back to scraping the main project website if no docs URL is found.
    Writes results to state['documentation_data'].
    """
    project_name = state.get("project_name", "")
    project_urls = state.get("project_urls", {})
    lang = state.get("lang", "ru")
    user_settings = state.get("user_settings", {}) or {}
    max_pages = int(user_settings.get("docs_max_pages", 30))
    log.info("documentation.start", project=project_name, max_pages=max_pages)

    from src.agents.graph import push_step

    documentation_data: dict = {}
    errors = list(state.get("errors", []))

    try:
        from src.services.scraper import DocumentationScraper
        from src.services.llm import LLMService

        scraper = DocumentationScraper()
        llm = LLMService()

        # Resolve project URLs if website is not available in state
        _has_any_docs_url = any(project_urls.get(k) for k in ("docs", "gitbook", "whitepaper", "documentation", "litepaper", "wiki", "notion"))
        if not project_urls.get("website") and not _has_any_docs_url:
            await push_step("documentation", _step("search_links", lang))
            from src.agents.resolve_urls import resolve_project_urls
            project_urls = await resolve_project_urls(project_name, project_urls)
            log.info("documentation.resolved_urls", project=project_name, urls=project_urls)

        # Collect all candidate website URLs (used for both discovery and fallback)
        _website_candidates = [
            v for k, v in project_urls.items()
            if k in ("website", "web", "homepage") and v
        ]

        # Discover docs URL if not already known.
        # Check all doc-related URL keys, not just "docs".
        _DOCS_KEYS = ("docs", "gitbook", "whitepaper", "documentation", "litepaper", "wiki", "notion")
        docs_url = next((project_urls[k] for k in _DOCS_KEYS if project_urls.get(k)), None)
        if docs_url:
            log.info("documentation.url_from_project_urls", project=project_name, docs_url=docs_url)
        if not docs_url:
            if _website_candidates:
                await push_step("documentation", _step("search_docs", lang))
                for _site in _website_candidates:
                    docs_url = await scraper.discover_docs_url(_site)
                    if docs_url:
                        log.info("documentation.url_discovered", project=project_name, docs_url=docs_url, via=_site)
                        break
                if not docs_url:
                    log.info("documentation.discover_failed", project=project_name, tried=_website_candidates)
            else:
                log.info("documentation.no_website_to_discover", project=project_name)

        async def _on_page(url: str) -> None:
            short = url if len(url) <= 60 else url[:57] + "…"
            await push_step("documentation", _step("reading_page", lang, url=short))

        if docs_url:
            log.info("documentation.url_found", project=project_name, docs_url=docs_url)
            await push_step("documentation", _step("found_docs", lang, url=docs_url))

            pages = await scraper.scrape_docs_pages(docs_url, max_pages=max_pages, on_page=_on_page)
            combined_text = "\n\n".join(p.text_content for p in pages)
            combined_text = combined_text[:50_000]

            if combined_text.strip():
                merged_links: dict[str, str] = {}
                for p in pages:
                    for label, url in p.external_links.items():
                        if label not in merged_links:
                            merged_links[label] = url

                await push_step("documentation", _step("analysing", lang, n=len(pages)))
                result = await llm.analyze_documentation(
                    task_prompt=DOCUMENTATION_PROMPT.format(
                        lang_instruction=_lang_instruction(lang), text=combined_text
                    ),
                )
                documentation_data = result
                documentation_data["scraped_pages"] = [p.url for p in pages]
                documentation_data["docs_url"] = docs_url
                if merged_links:
                    from src.services.scraper import _validate_external_links
                    valid_links = await _validate_external_links(merged_links)
                    if valid_links:
                        documentation_data["project_links"] = valid_links
                        log.info("documentation.links_validated", total=len(merged_links), valid=len(valid_links), project=project_name)
            else:
                documentation_data["error"] = "Pages found but no text extracted"

        elif _website_candidates:
            # Fallback: scrape the main project website when no docs URL was found
            website_url = _website_candidates[0]
            log.info("documentation.website_fallback", project=project_name, website=website_url)
            await push_step("documentation", _step("fallback_website", lang))

            pages = await scraper.scrape_docs_pages(website_url, max_pages=min(max_pages, 10), on_page=_on_page)
            combined_text = "\n\n".join(p.text_content for p in pages)
            combined_text = combined_text[:50_000]

            if combined_text.strip():
                await push_step("documentation", _step("analysing_website", lang, n=len(pages)))
                result = await llm.analyze_documentation(
                    task_prompt=WEBSITE_PROMPT.format(
                        lang_instruction=_lang_instruction(lang), text=combined_text
                    ),
                )
                documentation_data = result
                documentation_data["scraped_pages"] = [p.url for p in pages]
                documentation_data["scraped_from_website"] = True
                documentation_data["website_url"] = website_url
                log.info("documentation.website_fallback_done", project=project_name, pages=len(pages))
            else:
                documentation_data["error"] = "Website found but no text extracted"
                log.info("documentation.website_fallback_empty", project=project_name)
        else:
            log.info("documentation.no_docs_url", project=project_name)
            documentation_data["error"] = "No documentation or website URL found"

    except Exception as e:
        log.warning("documentation.failed", error=str(e))
        errors.append(f"Documentation: {e}")

    log.info("documentation.done", project=project_name, has_data=bool(documentation_data))

    return {
        **state,
        "documentation_data": documentation_data,
        "documentation_done": True,
        "errors": errors,
    }
