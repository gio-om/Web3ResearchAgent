"""
Documentation agent: scrapes and analyzes project documentation via Claude.
"""
import structlog

log = structlog.get_logger()

DOCUMENTATION_PROMPT = """Extract the following structured data from this project documentation.
Return ONLY valid JSON, no markdown fences, no extra text.

Extract:
{{
  "token_name": "<string>",
  "token_symbol": "<string or null>",
  "total_supply": <number or null>,
  "vesting_schedules": [
    {{
      "recipient_type": "<Team|Investors|Community|Treasury|Ecosystem|...>",
      "total_percent": <number — % of total supply>,
      "cliff_months": <number or null>,
      "vesting_months": <number or null>,
      "tge_percent": <number or null — % unlocked at TGE>
    }}
  ],
  "unusual_conditions": ["<risky or unusual vesting terms>"],
  "data_completeness": "<high|medium|low>"
}}

Documentation text:
{text}
"""


async def documentation_node(state: dict) -> dict:
    """
    Discovers, scrapes, and analyzes project documentation using LLM.
    Writes results to state['documentation_data'].
    """
    project_name = state.get("project_name", "")
    project_urls = state.get("project_urls", {})
    log.info("documentation.start", project=project_name)

    from src.agents.graph import push_step

    documentation_data: dict = {}
    errors = list(state.get("errors", []))

    try:
        from src.services.scraper import DocumentationScraper
        from src.services.llm import LLMService

        scraper = DocumentationScraper()
        llm = LLMService()

        # Discover docs URL if not already known
        docs_url = project_urls.get("docs")
        if not docs_url and project_urls.get("website"):
            await push_step("documentation", "Ищем страницу документации...")
            docs_url = await scraper.discover_docs_url(project_urls["website"])

        if docs_url:
            await push_step("documentation", "Читаем страницы с токеномикой...")
            pages = await scraper.scrape_tokenomics_pages(docs_url)

            # ScrapedPage dataclass → text
            combined_text = "\n\n".join(p.text_content for p in pages)
            combined_text = combined_text[:50_000]

            if combined_text.strip():
                await push_step("documentation", f"Анализируем документацию ({len(pages)} стр.) с AI...")
                result = await llm.analyze_documentation(
                    task_prompt=DOCUMENTATION_PROMPT.format(text=combined_text),
                )
                documentation_data = result
                documentation_data["scraped_pages"] = [p.url for p in pages]
                documentation_data["docs_url"] = docs_url
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
