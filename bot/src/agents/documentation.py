"""
Documentation agent: scrapes and analyzes project documentation via Claude.
"""
import structlog

log = structlog.get_logger()

DOCUMENTATION_PROMPT = """You are a crypto analyst. Read the project documentation below and extract the most important and interesting information about the project.
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


_STEPS: dict[str, dict[str, str]] = {
    "search_links":    {"ru": "Ищем ссылки проекта...",        "en": "Searching project links..."},
    "search_docs":     {"ru": "Ищем страницу документации...", "en": "Searching docs page..."},
    "found_docs":      {"ru": "Найдена документация: {url}",   "en": "Found documentation: {url}"},
    "reading_pages":   {"ru": "Читаем страницы документации...", "en": "Reading documentation pages..."},
    "analysing":       {"ru": "Анализируем документацию ({n} стр.) с AI...", "en": "Analysing documentation ({n} pages) with AI..."},
}


def _step(key: str, lang: str, **kwargs) -> str:
    text = _STEPS[key].get(lang) or _STEPS[key]["ru"]
    return text.format(**kwargs) if kwargs else text


async def documentation_node(state: dict) -> dict:
    """
    Discovers, scrapes, and analyzes project documentation using LLM.
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
        if not project_urls.get("website") and not project_urls.get("docs"):
            await push_step("documentation", _step("search_links", lang))
            from src.agents.resolve_urls import resolve_project_urls
            project_urls = await resolve_project_urls(project_name, project_urls)
            log.info("documentation.resolved_urls", project=project_name, urls=project_urls)

        # Discover docs URL if not already known
        docs_url = project_urls.get("docs")
        if not docs_url and project_urls.get("website"):
            await push_step("documentation", _step("search_docs", lang))
            docs_url = await scraper.discover_docs_url(project_urls["website"])
            if docs_url:
                log.info("documentation.url_discovered", project=project_name, docs_url=docs_url)
            else:
                log.info("documentation.discover_failed", project=project_name, website=project_urls.get("website"))
        elif not docs_url:
            log.info("documentation.no_website_to_discover", project=project_name)

        if docs_url:
            log.info("documentation.url_found", project=project_name, docs_url=docs_url)
            await push_step("documentation", _step("found_docs", lang, url=docs_url))
            await push_step("documentation", _step("reading_pages", lang))
            pages = await scraper.scrape_docs_pages(docs_url, max_pages=max_pages)

            # ScrapedPage dataclass → text
            combined_text = "\n\n".join(p.text_content for p in pages)
            combined_text = combined_text[:50_000]

            if combined_text.strip():
                # Merge external links from all pages (first occurrence wins)
                merged_links: dict[str, str] = {}
                for p in pages:
                    for label, url in p.external_links.items():
                        if label not in merged_links:
                            merged_links[label] = url

                await push_step("documentation", _step("analysing", lang, n=len(pages)))
                result = await llm.analyze_documentation(
                    task_prompt=DOCUMENTATION_PROMPT.format(text=combined_text),
                )
                documentation_data = result
                documentation_data["scraped_pages"] = [p.url for p in pages]
                documentation_data["docs_url"] = docs_url
                if merged_links:
                    documentation_data["project_links"] = merged_links
                    log.info("documentation.links_found", count=len(merged_links), project=project_name)
            else:
                documentation_data["error"] = "Pages found but no text extracted"
        else:
            log.info("documentation.no_docs_url", project=project_name)
            documentation_data["error"] = "No documentation URL found"

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
