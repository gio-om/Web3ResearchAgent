"""
LLM wrapper via OmniRoute using the OpenAI SDK.
OmniRoute exposes an OpenAI-compatible endpoint at /v1 and routes
requests to the configured provider/model transparently.

All public methods:
- Return structured Python objects (dict/list/str), never raw API responses.
- Retry up to MAX_RETRIES times with exponential backoff.
- Strip markdown code fences from responses before JSON parsing.
- Raise LLMError on unrecoverable failures.
"""
import asyncio
import json
import re
from typing import Any

import structlog
from openai import AsyncOpenAI, APIStatusError, APIConnectionError, RateLimitError

from src.config import settings

log = structlog.get_logger()

MAX_RETRIES = 3
MAX_TOKENS = 4096
BASE_RETRY_DELAY = 1.0  # seconds

SYSTEM_JSON = (
    "You are a precise data extraction assistant. "
    "Always respond with valid JSON only — no markdown fences, no prose, no extra keys. "
    "If data is missing, use null. Never truncate arrays."
)


class LLMError(Exception):
    """Raised when all retries are exhausted or a non-retryable error occurs."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_json(raw: str, context: str = "") -> Any:
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        log.warning("llm.json_parse_failed", context=context, raw=cleaned[:300])
        raise LLMError(f"Could not parse JSON from LLM response ({context})")


class LLMService:
    """Async LLM client routed through OmniRoute (OpenAI-compatible)."""

    def __init__(self) -> None:
        self._model = settings.OMNIROUTE_MODEL
        self._client = AsyncOpenAI(
            api_key=settings.OMNIROUTE_API_KEY,
            base_url=settings.OMNIROUTE_BASE_URL,  # http://omniroute:20128/v1
        )
        log.info("llm.init", model=self._model, base_url=settings.OMNIROUTE_BASE_URL)

    async def _call(
        self,
        prompt: str,
        *,
        system: str = SYSTEM_JSON,
        max_tokens: int = MAX_TOKENS,
    ) -> str:
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content or ""

            except RateLimitError:
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                log.warning("llm.rate_limit", attempt=attempt + 1, retry_in=delay)
                await asyncio.sleep(delay)

            except APIConnectionError as e:
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                log.warning("llm.connection_error", attempt=attempt + 1, error=str(e))
                if attempt == MAX_RETRIES - 1:
                    raise LLMError(f"LLM connection failed: {e}") from e
                await asyncio.sleep(delay)

            except APIStatusError as e:
                if e.status_code == 429:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    log.warning("llm.rate_limit", attempt=attempt + 1, retry_in=delay)
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(f"LLM API error {e.status_code}: {e.message}") from e

        raise LLMError(f"LLM call failed after {MAX_RETRIES} attempts")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def extract_json(self, prompt: str, context: str = "") -> Any:
        raw = await self._call(prompt)
        return _parse_json(raw, context=context)

    async def analyze_documentation(self, task_prompt: str) -> dict:
        raw = await self._call(task_prompt)
        try:
            result = _parse_json(raw, context="analyze_documentation")
            return result if isinstance(result, dict) else {"raw": result}
        except LLMError:
            return {"error": "parse_failed", "raw": raw[:500]}

    async def analyze_sentiment(self, tweets: list[str], project_name: str, lang: str = "ru") -> dict:
        if not tweets:
            return {
                "sentiment_score": 0.0,
                "key_concerns": [],
                "positive_signals": [],
                "notable_supporters": [],
                "overall_assessment": "No tweets available",
            }

        lang_instruction = (
            "Write all text fields (key_concerns, positive_signals, bot_activity_signals, overall_assessment) in Russian. "
            "Keep terms like Twitter, Discord, KOL, FDV, MCap, TGE, DeFi, NFT, DAO as-is."
            if lang == "ru" else
            "Write all text fields in English. "
            "Keep terms like Twitter, Discord, KOL, FDV, MCap, TGE, DeFi, NFT, DAO as-is."
        )

        tweets_block = "\n---\n".join(tweets[:40])
        prompt = f"""Analyze sentiment and social signals for crypto project "{project_name}".
{lang_instruction}

Tweets:
{tweets_block}

Return JSON:
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "key_concerns": ["<concern>"],
  "positive_signals": ["<signal>"],
  "notable_supporters": ["<KOL name or handle>"],
  "bot_activity_signals": ["<signal if any>"],
  "overall_assessment": "<1 sentence>"
}}"""
        raw = await self._call(prompt)
        try:
            result = _parse_json(raw, context="analyze_sentiment")
            return result if isinstance(result, dict) else {}
        except LLMError:
            return {"sentiment_score": 0.0, "key_concerns": [], "positive_signals": [], "notable_supporters": []}

    async def normalize_project_query(self, user_input: str) -> dict:
        prompt = f"""The user wants to analyze a crypto project. Their input: "{user_input}"

Extract:
{{
  "project_name": "<canonical name, e.g. LayerZero>",
  "project_slug": "<lowercase-hyphenated, e.g. layerzero>",
  "possible_website": "<URL or null>",
  "possible_twitter": "<@handle or URL or null>"
}}"""
        raw = await self._call(prompt)
        try:
            return _parse_json(raw, context="normalize_project_query")
        except LLMError:
            slug = user_input.lower().strip().replace(" ", "-")
            return {"project_name": user_input, "project_slug": slug,
                    "possible_website": None, "possible_twitter": None}

    async def extract_team_members(self, page_content: str) -> list[dict]:
        if not page_content.strip():
            return []

        prompt = f"""Extract all team members from this project page content.

Return a JSON array (empty [] if no team info found):
[
  {{
    "name": "<full name>",
    "role": "<job title>",
    "linkedin_url": "<URL or null>",
    "previous_companies": ["<company name>"],
    "profile_notes": "<any notable background>"
  }}
]

Content:
{page_content[:15_000]}"""
        raw = await self._call(prompt)
        try:
            result = _parse_json(raw, context="extract_team_members")
            return result if isinstance(result, list) else []
        except LLMError:
            return []

    async def extract_team_from_search_results(
        self, search_results: list[dict], project_name: str
    ) -> list[dict]:
        """
        Extract structured team members from DDG search result titles/snippets.
        Each result: {title, snippet, url} from a LinkedIn profile search.
        """
        if not search_results:
            return []

        lines = []
        for i, r in enumerate(search_results, 1):
            lines.append(
                f"{i}. Title: {r['title']}\n"
                f"   Snippet: {r['snippet']}\n"
                f"   URL: {r['url']}"
            )
        block = "\n\n".join(lines)

        prompt = f"""These are web search results for LinkedIn profiles of people working at crypto project "{project_name}".
Each result is a LinkedIn profile page.

Extract only people who currently work at "{project_name}" (ignore past employees).

Return JSON array (empty [] if none found):
[
  {{
    "name": "<full name>",
    "role": "<current job title>",
    "linkedin_url": "<linkedin profile URL>",
    "previous_companies": ["<company name>"],
    "profile_notes": "<any notable background from snippet>"
  }}
]

Search results:
{block}"""

        raw = await self._call(prompt)
        try:
            result = _parse_json(raw, context="extract_team_from_search_results")
            return result if isinstance(result, list) else []
        except LLMError:
            return []

    async def extract_linkedin_company_data(self, page_content: str) -> dict:
        if not page_content.strip():
            return {}

        prompt = f"""Extract company information from this LinkedIn company page content.

Return JSON:
{{
  "employee_count_range": "<e.g. '51-200' or null>",
  "members": [
    {{
      "name": "<full name>",
      "role": "<job title>",
      "linkedin_url": "<URL or null>",
      "previous_companies": ["<company name>"],
      "profile_notes": "<any notable background>"
    }}
  ],
  "company_description": "<brief description or null>"
}}

Content:
{page_content[:15_000]}"""
        raw = await self._call(prompt)
        try:
            result = _parse_json(raw, context="extract_linkedin_company_data")
            return result if isinstance(result, dict) else {}
        except LLMError:
            return {}

    async def generate_final_report(
        self,
        project_name: str,
        aggregator_data: dict,
        documentation_data: dict,
        social_data: dict,
        team_data: dict,
        cross_check_results: list,
        lang: str = "ru",
    ) -> dict:
        lang_instruction = (
            "Write summary, strengths, and weaknesses in Russian. "
            "Keep terms like FDV, MCap, TVL, TGE, Twitter, Discord, GitHub, DAO, DeFi, NFT, KOL, Tier-1 as-is."
            if lang == "ru" else
            "Write summary, strengths, and weaknesses in English. "
            "Keep terms like FDV, MCap, TVL, TGE, Twitter, Discord, GitHub, DAO, DeFi, NFT, KOL, Tier-1 as-is."
        )

        prompt = f"""You are a professional crypto analyst. Evaluate project "{project_name}".
{lang_instruction}

Aggregator data: {json.dumps(aggregator_data, ensure_ascii=False)[:2500]}
Documentation: {json.dumps(documentation_data, ensure_ascii=False)[:1500]}
Social metrics: {json.dumps(social_data, ensure_ascii=False)[:800]}
Team: {json.dumps(team_data, ensure_ascii=False)[:800]}
Risk flags: {json.dumps(cross_check_results, ensure_ascii=False)[:800]}

Return JSON:
{{
  "overall_score": <integer 0-100>,
  "recommendation": "<DYOR|Interesting|Strong|Avoid>",
  "summary": "<3-4 sentences>",
  "strengths": ["<point>"],
  "weaknesses": ["<point>"],
  "tokenomics_score": <0-25>,
  "investors_score": <0-25>,
  "team_score": <0-25>,
  "social_score": <0-25>
}}"""
        raw = await self._call(prompt)
        try:
            result = _parse_json(raw, context="generate_final_report")
            return result if isinstance(result, dict) else {}
        except LLMError:
            return {
                "overall_score": 0,
                "recommendation": "DYOR",
                "summary": "Analysis incomplete due to LLM error.",
                "strengths": [],
                "weaknesses": [],
            }
