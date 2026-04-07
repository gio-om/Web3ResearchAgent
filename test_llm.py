"""
Quick connectivity test for the LLM API via LLMService.
Run from web3-dd-bot/ directory:
    python test_llm.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

# Patch settings before importing LLMService
import src.config as _cfg
_cfg.settings.ANTHROPIC_API_KEY = "cr_b528e74d4b5ab8c7a5fb15e6cb13957428aa20d43b4e83f68ec8648fad9dd539"
_cfg.settings.ANTHROPIC_BASE_URL = "https://api.orcai.cc/v1"
_cfg.settings.ANTHROPIC_PROXY_URL = ""
_cfg.settings.CLAUDE_MODEL = "claude-sonnet-4-6"

from src.services.llm import LLMService


async def main():
    print("Testing LLMService with orcai.cc (raw httpx mode)...")
    llm = LLMService()
    print(f"  use_raw={llm._use_raw}, base_url={llm._base_url}")

    try:
        result = await llm.extract_json(
            'Return JSON: {"status": "ok", "message": "hello from claude"}',
            context="test"
        )
        print("SUCCESS:", result)
    except Exception as e:
        print("FAILED:", type(e).__name__, str(e)[:300])


asyncio.run(main())
