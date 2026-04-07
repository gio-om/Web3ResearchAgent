"""
Wrapper over Anthropic Claude API (or compatible proxy such as orcai.cc).

Uses raw httpx when ANTHROPIC_BASE_URL is set — avoids Anthropic-SDK headers
that some proxy services reject. Falls back to the official SDK otherwise.

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

import httpx
import structlog

from src.config import settings

log = structlog.get_logger()

MAX_RETRIES = 3
MAX_TOKENS = 4096
BASE_RETRY_DELAY = 1.0  # seconds

# Injected into every LLM call to enforce JSON output
SYSTEM_JSON = (
    "You are a precise data extraction assistant. "
    "Always respond with valid JSON only — no markdown fences, no prose, no extra keys. "
    "If data is missing, use null. Never truncate arrays."
)

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)


class LLMError(Exception):
    """Raised when all retries are exhausted or a non-retryable error occurs."""


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_json(raw: str, context: str = "") -> Any:
    """Parse JSON with a fallback that tries to extract the first {...} or [...] block."""
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract first valid JSON object/array
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        log.warning("llm.json_parse_failed", context=context, raw=cleaned[:300])
        raise LLMError(f"Could not parse JSON from LLM response ({context})")


async def _call_raw_httpx(
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    prompt: str,
    max_tokens: int,
) -> str:
    """
    Call Anthropic-compatible API via raw httpx (no SDK).
    Works with proxies like orcai.cc that block SDK-specific headers.
    """
    url = base_url.rstrip("/") + "/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(url, headers=headers, json=body)
    if r.status_code == 429:
        raise LLMError("rate_limit")
    if r.status_code >= 400:
        raise LLMError(f"API error {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data["content"][0]["text"]


class LLMService:
    """
    Async wrapper around Anthropic Claude API (or compatible proxy).
    Uses raw httpx when ANTHROPIC_BASE_URL is set; official SDK otherwise.
    """

    def __init__(self) -> None:
        self._model = settings.CLAUDE_MODEL
        self._api_key = settings.ANTHROPIC_API_KEY
        self._base_url = settings.ANTHROPIC_BASE_URL or ""
        self._use_raw = bool(self._base_url)  # raw httpx for proxy endpoints

        if not self._use_raw:
            from anthropic import AsyncAnthropic
            self._sdk_client = AsyncAnthropic(
                api_key=self._api_key,
                http_client=httpx.AsyncClient(timeout=_TIMEOUT),
            )

    # ------------------------------------------------------------------
    # Core private call
    # ------------------------------------------------------------------

    async def _call(
        self,
        prompt: str,
        *,
        system: str = SYSTEM_JSON,
        max_tokens: int = MAX_TOKENS,
    ) -> str:
        """
        Send a message to Claude and return the text response.
        Retries on transient errors. Raises LLMError on permanent failure.
        """
        for attempt in range(MAX_RETRIES):
            try:
                if self._use_raw:
                    return await _call_raw_httpx(
                        base_url=self._base_url,
                        api_key=self._api_key,
                        model=self._model,
                        system=system,
                        prompt=prompt,
                        max_tokens=max_tokens,
                    )
                else:
                    from anthropic import APIConnectionError, APIStatusError, RateLimitError
                    response = await self._sdk_client.messages.create(
                        model=self._model,
                        max_tokens=max_tokens,
                        system=system,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return response.content[0].text

            except LLMError as e:
                if "rate_limit" in str(e):
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    log.warning("llm.rate_limit", attempt=attempt + 1, retry_in=delay)
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.TimeoutException as e:
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                log.warning("llm.timeout", attempt=attempt + 1, retry_in=delay)
                if attempt == MAX_RETRIES - 1:
                    raise LLMError(f"Claude timed out after {MAX_RETRIES} attempts") from e
                await asyncio.sleep(delay)
            except httpx.HTTPError as e:
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                log.warning("llm.connection_error", attempt=attempt + 1, error=str(e), retry_in=delay)
                if attempt == MAX_RETRIES - 1:
                    raise LLMError(f"Claude connection failed: {e}") from e
                await asyncio.sleep(delay)
            except Exception as e:
                # For SDK path: catch RateLimitError, APIConnectionError, APIStatusError
                name = type(e).__name__
                if "RateLimit" in name:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    log.warning("llm.rate_limit", attempt=attempt + 1, retry_in=delay)
                    await asyncio.sleep(delay)
                    continue
                if "Connection" in name:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    log.warning("llm.connection_error", attempt=attempt + 1, error=str(e))
                    if attempt == MAX_RETRIES - 1:
                        raise LLMError(f"Claude connection failed: {e}") from e
                    await asyncio.sleep(delay)
                    continue
                log.error("llm.unexpected_error", error=str(e), type=name)
                raise LLMError(f"Claude error: {e}") from e

        raise LLMError(f"Claude call failed after {MAX_RETRIES} attempts")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def extract_json(self, prompt: str, context: str = "") -> Any:
        """
        Generic JSON extraction. Returns parsed dict or list.
        Use this when you need structured data from an ad-hoc prompt.
        """
        raw = await self._call(prompt)
        return _parse_json(raw, context=context)

    async def analyze_documentation(self, task_prompt: str) -> dict:
        """
        Analyze a block of text (tokenomics docs, whitepaper) and return structured dict.
        `task_prompt` should already include the text to analyze.
        """
        raw = await self._call(task_prompt)
        try:
            result = _parse_json(raw, context="analyze_documentation")
            return result if isinstance(result, dict) else {"raw": result}
        except LLMError:
            return {"error": "parse_failed", "raw": raw[:500]}

    async def analyze_sentiment(
        self,
        tweets: list[str],
        project_name: str,
    ) -> dict:
        """
        Analyze sentiment of a list of tweet texts.
        Returns a dict with sentiment_score, key_concerns, positive_signals, notable_supporters.
        """
        if not tweets:
            return {
                "sentiment_score": 0.0,
                "key_concerns": [],
                "positive_signals": [],
                "notable_supporters": [],
                "overall_assessment": "No tweets available",
            }

        tweets_block = "\n---\n".join(tweets[:40])
        prompt = f"""Analyze sentiment and social signals for crypto project "{project_name}".

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
            return {
                "sentiment_score": 0.0,
                "key_concerns": [],
                "positive_signals": [],
                "notable_supporters": [],
            }

    async def normalize_project_query(self, user_input: str) -> dict:
        """
        Extract canonical project name and slug from arbitrary user input.
        Returns {"project_name": str, "project_slug": str,
                 "possible_website": str|None, "possible_twitter": str|None}
        """
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
        """
        Extract team members from About/Team page content.
        Returns list of {"name", "role", "linkedin_url", "previous_companies", "profile_notes"}.
        """
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

    async def generate_final_report(
        self,
        project_name: str,
        aggregator_data: dict,
        documentation_data: dict,
        social_data: dict,
        team_data: dict,
        cross_check_results: list,
    ) -> dict:
        """
        Generate the final analyst report with scoring and recommendation.
        Returns {"overall_score", "recommendation", "summary", "strengths",
                 "weaknesses", "tokenomics_score", "investors_score",
                 "team_score", "social_score"}.
        """
        prompt = f"""You are a professional crypto analyst. Evaluate project "{project_name}".

Aggregator data: {json.dumps(aggregator_data, ensure_ascii=False)[:2500]}
Documentation: {json.dumps(documentation_data, ensure_ascii=False)[:1500]}
Social metrics: {json.dumps(social_data, ensure_ascii=False)[:800]}
Team: {json.dumps(team_data, ensure_ascii=False)[:800]}
Risk flags: {json.dumps(cross_check_results, ensure_ascii=False)[:800]}

Return JSON:
{{
  "overall_score": <integer 0-100>,
  "recommendation": "<DYOR|Interesting|Strong|Avoid>",
  "summary": "<3-4 sentences in Russian>",
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
