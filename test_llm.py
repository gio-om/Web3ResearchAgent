"""
Quick test: Claude & GPT via ORCA (orcai.cc)
Run from repo root:  python test_llm.py

If you get 404 on Claude/GPT — your API key is expired or invalid.
Go to https://orcai.cc/dashboard -> create a new key -> update .env
"""
import asyncio
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(".env")

API_KEY  = os.getenv("OPENAI_API_KEY", "")  # same key for both providers on ORCA
BASE_URL = "https://api.orcai.cc"
TIMEOUT  = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
PROMPT   = "Say hello in one sentence."

OK  = "[OK]  "
ERR = "[ERR] "
INF = "[---] "


# ─────────────────────────── Service status ──────────────────────────────────

async def check_status() -> bool:
    """Returns True if ORCA service is up."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{BASE_URL}/v1/status")
    if r.status_code == 200:
        data = r.json().get("data", {})
        overall = data.get("overallStatus", "unknown")
        services = data.get("services", [])
        print(f"{OK}ORCA status: {overall}")
        for svc in services:
            print(f"  {svc['key']:8s}  {svc['status']:4s}  models: {[m['label'] for m in svc.get('availableModels', [])]}")
        return True
    else:
        print(f"{ERR}Status check failed: {r.status_code}")
        return False


# ──────────────────────────── Claude ─────────────────────────────────────────

async def test_claude(model: str = "claude-sonnet-4-6") -> bool:
    url = f"{BASE_URL}"
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 1024,
        "system": "You are a helpful assistant.",
        "messages": [{"role": "user", "content": PROMPT}],
    }
    print(f"\n{INF}[Claude] model={model}")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(url, headers=headers, json=body)

    if r.status_code == 200:
        text = r.json()["content"][0]["text"]
        print(f"{OK}reply: {text.strip()}")
        return True
    else:
        hint = ""
        if r.status_code == 404:
            hint = " (key expired? -> orcai.cc/dashboard)"
        print(f"{ERR}HTTP {r.status_code}{hint}")
        print(f"      {r.text[:300]}")
        return False


# ──────────────────────────── GPT (streaming) ────────────────────────────────

async def test_gpt(model: str = "gpt-5.1-codex") -> bool:
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 256,
        "stream": True,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": PROMPT},
        ],
    }
    print(f"\n{INF}[GPT]   model={model}")
    parts: list[str] = []
    status_code = None

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async with client.stream("POST", url, headers=headers, json=body) as r:
            status_code = r.status_code
            if r.status_code >= 400:
                body_bytes = await r.aread()
                hint = ""
                if r.status_code == 404:
                    hint = " (key expired? -> orcai.cc/dashboard)"
                print(f"{ERR}HTTP {r.status_code}{hint}")
                print(f"      {body_bytes[:300].decode(errors='replace')}")
                return False

            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk_str = line[5:].strip()
                if chunk_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(chunk_str)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    parts.append(delta["content"])
                if delta.get("reasoning_content"):
                    parts.append(delta["reasoning_content"])

    reply = "".join(parts)
    if reply:
        print(f"{OK}reply: {reply.strip()}")
        return True
    else:
        print(f"{ERR}Empty response (status {status_code})")
        return False


# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    if not API_KEY:
        print(f"{ERR}API_KEY is empty — check .env (OPENAI_API_KEY)")
        sys.exit(1)

    print(f"ORCA key : {API_KEY[:12]}...")
    print(f"BASE_URL : {BASE_URL}\n")

    await check_status()

    claude_ok = await test_claude()
    gpt_ok    = await test_gpt()

    print(f"\n{'='*40}")
    print(f"Claude : {'OK' if claude_ok else 'FAIL'}")
    print(f"GPT    : {'OK' if gpt_ok    else 'FAIL'}")

    if not claude_ok or not gpt_ok:
        print("\nIf you see 404: key is expired -> orcai.cc/dashboard -> create new key -> update .env")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
