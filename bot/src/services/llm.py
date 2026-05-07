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
import hashlib
import json
import re
from datetime import datetime, timezone
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

    async def extract_team_members(self, page_content: str, lang: str = "ru") -> list[dict]:
        if not page_content.strip():
            return []

        lang_instruction = (
            "Write role and profile_notes in Russian."
            if lang == "ru" else
            "Write role and profile_notes in English."
        )

        prompt = f"""Extract all team members from this project page content.
{lang_instruction}

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
                "summary": "Анализ не завершён из-за ошибки LLM." if lang == "ru" else "Analysis incomplete due to LLM error.",
                "strengths": [],
                "weaknesses": [],
            }

    async def predict_fdv(
        self,
        round_data: dict,
        project_context: dict,
        user_context: dict,
        comparable_rounds: list[dict],
        coingecko_fdv: float | None,
        lang: str = "ru",
    ) -> dict:
        """Predict FDV for a funding round where valuation_usd is None.

        Returns dict with predicted_fdv_usd, fdv_range_low_usd, fdv_range_high_usd,
        confidence (low|medium|high), confidence_score, methodology, key_assumptions,
        implied_multiple.
        Returns {} on failure.
        """
        # Shortcut: token_price × total_supply avoids LLM entirely
        token_price = round_data.get("token_price")
        total_supply = project_context.get("max_supply")
        if token_price and total_supply:
            try:
                fdv = float(token_price) * float(total_supply)
                return {
                    "predicted_fdv_usd": int(fdv),
                    "fdv_range_low_usd": int(fdv * 0.9),
                    "fdv_range_high_usd": int(fdv * 1.1),
                    "confidence": "high",
                    "confidence_score": 0.95,
                    "methodology": (
                        "Вычислено напрямую: цена токена × общий supply."
                        if lang == "ru" else
                        "Computed directly: token_price × total_supply."
                    ),
                    "key_assumptions": [],
                    "implied_multiple": round(fdv / round_data["amount_usd"], 1) if round_data.get("amount_usd") else None,
                }
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        lang_instruction = (
            "Write methodology and key_assumptions in Russian. "
            "Keep terms like FDV, MCap, Seed, Series A, TGE, DeFi, L1, L2, DAO as-is."
            if lang == "ru" else
            "Write methodology and key_assumptions in English. "
            "Keep terms like FDV, MCap, Seed, Series A, TGE, DeFi, L1, L2, DAO as-is."
        )

        anchors_block = ""
        if coingecko_fdv:
            anchors_block += f"\nCurrent live FDV (CoinGecko): ${coingecko_fdv:,.0f} — use as reference for post-TGE trajectory."
        if comparable_rounds:
            lines = []
            for r in comparable_rounds[:5]:
                lines.append(f"  - {r.get('round_name', 'Round')} ({r.get('date', '?')}): raised ${r.get('amount_usd') or 0:,.0f}, valuation ${r.get('valuation_usd') or 0:,.0f}")
            anchors_block += "\nKnown valuations for same project:\n" + "\n".join(lines)
        if user_context.get("comparable_fdv_usd"):
            anchors_block += f"\nUser-provided comparable FDV anchor: ${user_context['comparable_fdv_usd']:,.0f}"

        user_ctx_block = ""
        if user_context.get("sector"):
            user_ctx_block += f"\n- Sector: {user_context['sector']}"
        if total_supply:
            user_ctx_block += f"\n- Total token supply: {total_supply:,}"

        investors_str = ""
        for inv in (round_data.get("investors") or [])[:10]:
            name = inv.get("name", inv) if isinstance(inv, dict) else str(inv)
            tier = inv.get("tier") if isinstance(inv, dict) else None
            investors_str += f"\n  - {name}" + (f" (Tier {tier})" if tier else "")

        prompt = f"""You are a senior crypto venture analyst specializing in pre-TGE token valuations.
{lang_instruction}

## Round being valued
- Round type: {round_data.get('round_name') or round_data.get('round_type', 'Unknown')}
- Date: {round_data.get('date', 'Unknown')}
- Amount raised: ${round_data.get('amount_usd') or 0:,.0f}
- Investors:{investors_str if investors_str else ' unknown'}

## Project context
- Name: {project_context.get('project_name', 'Unknown')}
- Category: {project_context.get('category') or 'Unknown'}
- Token symbol: {project_context.get('token_symbol') or 'Unknown'}

## User-provided context{user_ctx_block if user_ctx_block else chr(10) + '- No additional context provided'}

## Anchor data{anchors_block if anchors_block else chr(10) + '- No anchor data available'}

## Instructions
Use comparable-transactions methodology:
- Infer the market cycle from the round date (e.g. Nov 2021 = peak bull, 2022 = bear, 2023 H1 = neutral, 2023 H2–2024 = bull, 2025 = neutral/bear)
- Infer the product stage from the round type (Seed/Pre-Seed = idea or testnet, Series A = mainnet-early, Series B+ = mainnet-mature)
- Assess lead investor quality from the investor list provided above
- For bear market: apply 0.3–0.5x to median sector valuations
- For neutral market: apply 0.8–1.2x to median sector valuations
- For bull market: apply 1.5–3x to median sector valuations
- For peak bull: apply 3–5x to median sector valuations
- Consider the implied multiple (FDV / amount_raised): typical Seed = 20–100x, Series A = 10–40x
- Provide a range (low/high), not just a point estimate
- Be explicit about key assumptions

Return JSON only:
{{
  "predicted_fdv_usd": <integer>,
  "fdv_range_low_usd": <integer>,
  "fdv_range_high_usd": <integer>,
  "confidence": "<low|medium|high>",
  "confidence_score": <float 0.0-1.0>,
  "methodology": "<1-2 sentences>",
  "key_assumptions": ["<assumption>"],
  "implied_multiple": <float>
}}"""

        raw = await self._call(prompt, max_tokens=1024)
        try:
            result = _parse_json(raw, context="predict_fdv")
            if not isinstance(result, dict) or "predicted_fdv_usd" not in result:
                return {}
            # Apply deterministic confidence scoring on top of LLM value
            base = 0.5
            if total_supply:
                base += 0.15
            if comparable_rounds:
                base += 0.10
            if coingecko_fdv:
                base += 0.10
            if user_context.get("comparable_fdv_usd"):
                base += 0.10
            round_date = round_data.get("date") or ""
            if round_date:
                try:
                    age_years = (datetime.now(timezone.utc) - datetime.fromisoformat(round_date.replace("Z", "+00:00"))).days / 365
                    if age_years > 3:
                        base -= 0.15
                except (ValueError, TypeError):
                    pass
            if (user_context.get("sector") or "").lower() == "other":
                base -= 0.10
            conf_score = round(max(0.1, min(0.9, base)), 2)
            conf_label = "high" if conf_score >= 0.7 else ("medium" if conf_score >= 0.45 else "low")
            result["confidence_score"] = conf_score
            result["confidence"] = conf_label
            return result
        except LLMError:
            log.warning("llm.predict_fdv_failed", round=round_data.get("round_name"))
            return {}
