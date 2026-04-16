"""
LangGraph multi-agent pipeline.

Graph topology:
    START → orchestrator → dispatcher → cross_check → analyst → END

The dispatcher node runs aggregator, documentation, social, and team agents
concurrently via asyncio.gather, then merges their results into a single
state dict before passing it to cross_check.
"""
import asyncio
import structlog
from typing import TYPE_CHECKING

from langgraph.graph import END, StateGraph

if TYPE_CHECKING:
    from aiogram import Bot

# Set by main.py after bot creation so dispatcher can push live updates
_bot: "Bot | None" = None

# Shared progress context — written by dispatcher, read by push_step
_progress: dict = {
    "chat_id": None,
    "message_id": None,
    "project_name": "",
    "modules": [],
    "done": set(),
    "failed": set(),
    "steps": {},  # agent_name → current sub-step text
}


def set_bot(bot: "Bot") -> None:
    global _bot
    _bot = bot


def _build_progress_text() -> str:
    p = _progress
    lines = [f"🔍 <b>Анализ проекта: {p['project_name']}</b>\n"]
    for m in p["modules"]:
        if m in p["done"]:
            icon, step = "✅", ""
        elif m in p["failed"]:
            icon, step = "❌", ""
        else:
            icon = "⏳"
            step = p["steps"].get(m, "")
        label = _MODULE_LABEL[m]
        if step:
            lines.append(f"{icon} {label}...\n   └ <i>{step}</i>")
        else:
            lines.append(f"{icon} {label}...")
    return "\n".join(lines)


async def _do_edit() -> None:
    if _bot is None:
        return
    chat_id = _progress["chat_id"]
    message_id = _progress["message_id"]
    if not chat_id or not message_id:
        return
    try:
        await _bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_build_progress_text(),
        )
    except Exception:
        pass


async def push_step(agent_name: str, step_text: str) -> None:
    """Called by individual agents to report a sub-step; updates the Telegram progress message."""
    _progress["steps"][agent_name] = step_text
    await _do_edit()

from src.agents.orchestrator import orchestrator_node
from src.agents.aggregator import aggregator_node
from src.agents.documentation import documentation_node
from src.agents.social import social_node
from src.agents.team import team_node
from src.agents.cross_check import cross_check_node
from src.agents.analyst import analyst_node

log = structlog.get_logger()


_ALL_MODULES = ["aggregator", "documentation", "social", "team"]

_AGENT_FUNCS = [aggregator_node, documentation_node, social_node, team_node]

_AGENT_KEYS = [
    ("aggregator_data", "aggregator_done"),
    ("documentation_data", "documentation_done"),
    ("social_data", "social_done"),
    ("team_data", "team_done"),
]


_AGENT_TIMEOUT = 150  # seconds per agent

_MODULE_LABEL = {
    "aggregator":    "Сбор данных с агрегаторов",
    "documentation": "Анализ документации",
    "social":        "Проверка соцсетей",
    "team":          "Верификация команды",
}


async def _edit_progress(done: set[str], failed: set[str]) -> None:
    """Rebuild and push progress message after an agent finishes."""
    _progress["done"] = done
    _progress["failed"] = failed
    # Clear sub-step for finished agents
    for name in done | failed:
        _progress["steps"].pop(name, None)
    await _do_edit()


async def dispatcher_node(state: dict) -> dict:
    """
    Runs selected agents concurrently (controlled by state["enabled_modules"]).
    Updates Telegram progress message as each agent completes.
    Merges their results: data keys are taken from whichever agent set them,
    and the 'errors' lists are concatenated.
    """
    enabled = state.get("enabled_modules", _ALL_MODULES)
    log.info("dispatcher.start", project=state.get("project_name", ""), modules=enabled)

    # Initialise shared progress context for this run
    _progress["chat_id"] = state.get("chat_id")
    _progress["message_id"] = state.get("message_id")
    _progress["project_name"] = state.get("project_name") or state.get("project_query", "")
    _progress["modules"] = [m for m in _ALL_MODULES if m in enabled]
    _progress["done"] = set()
    _progress["failed"] = set()
    _progress["steps"] = {}

    # Wrap each agent: returns (index, result_or_exception)
    async def _run_agent(index: int, agent_name: str):
        try:
            result = await asyncio.wait_for(_AGENT_FUNCS[index](state), timeout=_AGENT_TIMEOUT)
            return index, result
        except asyncio.TimeoutError:
            log.error("dispatcher.agent_timeout", agent=agent_name, timeout=_AGENT_TIMEOUT)
            return index, TimeoutError(f"{agent_name} timed out after {_AGENT_TIMEOUT}s")
        except Exception as exc:
            log.error("dispatcher.agent_exception", agent=agent_name, error=str(exc))
            return index, exc

    active_indices = [i for i, n in enumerate(_ALL_MODULES) if n in enabled]
    tasks = [_run_agent(i, _ALL_MODULES[i]) for i in active_indices]

    merged = dict(state)
    merged_errors: list[str] = list(state.get("errors", []))
    done_names: set[str] = set()
    failed_names: set[str] = set()

    for coro in asyncio.as_completed(tasks):
        index, result = await coro
        agent_name = _ALL_MODULES[index]

        if isinstance(result, Exception):
            failed_names.add(agent_name)
            merged_errors.append(f"Agent[{agent_name}] crashed: {result}")
        else:
            done_names.add(agent_name)
            log.info("dispatcher.agent_done", agent=agent_name)
            for err in result.get("errors", []):
                if err not in merged_errors:
                    merged_errors.append(err)
            for key in _AGENT_KEYS[index]:
                if key in result:
                    merged[key] = result[key]
            # Merge project_urls from any agent: existing keys win, new keys are added
            if "project_urls" in result:
                current_urls = dict(merged.get("project_urls") or {})
                for k, v in (result["project_urls"] or {}).items():
                    if v and not current_urls.get(k):
                        current_urls[k] = v
                merged["project_urls"] = current_urls

        await _edit_progress(done_names, failed_names)

    merged["errors"] = merged_errors
    log.info("dispatcher.done", project=state.get("project_name", ""), errors=len(merged_errors))
    return merged


def build_analysis_graph():
    """Build and compile the multi-agent analysis graph."""
    graph = StateGraph(dict)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("dispatcher", dispatcher_node)
    graph.add_node("cross_check", cross_check_node)
    graph.add_node("analyst", analyst_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "dispatcher")
    graph.add_edge("dispatcher", "cross_check")
    graph.add_edge("cross_check", "analyst")
    graph.add_edge("analyst", END)

    return graph.compile()
