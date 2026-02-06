"""
MrDice ADK Agent entrypoint (client-side).

This module defines a Google ADK `root_agent` that connects to the running MrDice MCP server
over SSE (`SERVER_URL`) and can call the unified tool `mrdice_search`.

Notes
-----
- This is *not* the MCP server. The server entrypoint remains `python -m mrdice_server.server`.
- This file intentionally lives in the new package structure (not under tmp/).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    """
    Load environment variables from the project root `.env`.

    Do not rely on current working directory (ADK web server may run elsewhere).
    """
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        return

    # Fallback to CWD for compatibility
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=True)


_load_env()


def _bridge_llm_env_vars() -> None:
    """
    Bridge MrDice env var names to what LiteLLM expects.

    MrDice uses:
    - LLM_API_KEY / LLM_API_BASE

    LiteLLM integrations typically use provider-specific env vars:
    - DEEPSEEK_API_KEY / DEEPSEEK_API_BASE
    - OPENAI_API_KEY / OPENAI_API_BASE (OpenAI-compatible providers)
    """
    api_key = (os.getenv("LLM_API_KEY") or "").strip()
    api_base = (os.getenv("LLM_API_BASE") or "").strip()
    provider = (os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()

    if api_key:
        # DeepSeek provider env vars
        os.environ.setdefault("DEEPSEEK_API_KEY", api_key)
        # OpenAI-compatible fallback (many LiteLLM paths still read OPENAI_API_KEY)
        os.environ.setdefault("OPENAI_API_KEY", api_key)

    if api_base:
        os.environ.setdefault("DEEPSEEK_API_BASE", api_base)
        os.environ.setdefault("OPENAI_API_BASE", api_base)

    # Some setups use provider-specific key variables even when provider != deepseek.
    # Keep the mapping generic but harmless.
    if provider == "deepseek" and not os.getenv("DEEPSEEK_API_KEY") and api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key


_bridge_llm_env_vars()

# Enable nested asyncio when used in notebooks / embedded runtimes
try:
    import nest_asyncio

    nest_asyncio.apply()
except Exception:
    # Optional dependency / optional behavior
    pass


try:
    from google.adk.agents import LlmAgent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams

    from dp.agent.adapter.adk import CalculationMCPToolset
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Missing ADK dependencies. Make sure your environment provides "
        "`google-adk` and `dp.agent.adapter.adk` (usually via `bohrium-agents`)."
    ) from exc


# === Executors / Storage (kept consistent with historical agents) ===
BOHRIUM_EXECUTOR = {
    "type": "dispatcher",
    "machine": {
        "batch_type": "OpenAPI",
        "context_type": "OpenAPI",
        "remote_profile": {
            "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
            "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),  # strict: empty will raise
            "app_key": "agent",
            "image_address": "registry.dp.tech/dptech/dp/native/prod-19853/dpa-mcp:0.0.0",
            "platform": "ali",
            "machine_type": "",
        },
    },
    "resources": {"envs": {}},
}

HTTPS_STORAGE = {
    "type": "https",
    "plugin": {
        "type": "bohrium",
        "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
        "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),  # strict: empty will raise
        "app_key": "agent",
    },
}


# === Server URL from environment ===
server_url = (os.getenv("SERVER_URL") or "").strip()
if not server_url:
    raise RuntimeError("SERVER_URL is not set in environment (.env)")


# === Initialize MCP Toolset ===
mcp_tools = CalculationMCPToolset(
    connection_params=SseServerParams(url=server_url),
    storage=HTTPS_STORAGE,
)


def _litellm_model_id() -> str:
    """
    Build a LiteLLM model id from env.

    Examples:
    - LLM_PROVIDER=deepseek, LLM_MODEL=deepseek-chat -> "deepseek/deepseek-chat"
    - LLM_MODEL already has a slash -> used as-is
    """
    provider = (os.getenv("LLM_PROVIDER") or "deepseek").strip()
    model = (os.getenv("LLM_MODEL") or "deepseek/deepseek-chat").strip()
    if "/" in model:
        return model
    return f"{provider}/{model}"


# === Root LLM Agent ===
root_agent = LlmAgent(
    model=LiteLlm(model=_litellm_model_id()),
    name="MrDice_Agent",
    description="Unified materials search agent that calls MrDice MCP tool `mrdice_search`.",
    instruction=(
        "You can call one MCP tool exposed by the MrDice server:\n\n"
        "=== TOOL: mrdice_search ===\n"
        "Use this tool to search materials across multiple databases (OPTIMADE, MOFdb SQL, OpenLAM, Bohrium public).\n"
        "Arguments:\n"
        "• query: natural language query\n"
        "• n_results: number of results to return\n"
        "• output_format: 'cif' or 'json'\n\n"
        "Returns:\n"
        "• results: list of normalized items, each may contain `structure_file`\n"
        "• n_found / returned / fallback_level\n\n"
        "=== EXAMPLES ===\n"
        "1) 找一些 Fe2O3 材料，返回 3 个结构文件：\n"
        "   → Tool: mrdice_search\n"
        "     query: '找一些 Fe2O3 材料'\n"
        "     n_results: 3\n"
        "     output_format: 'cif'\n\n"
        "2) 搜索包含 Li 和 O 的电池材料，给我全部信息：\n"
        "   → Tool: mrdice_search\n"
        "     query: '搜索包含 Li 和 O 的电池材料'\n"
        "     n_results: 5\n"
        "     output_format: 'json'\n\n"
        "=== ANSWER FORMAT ===\n"
        "1. Summarize the query intent\n"
        "2. Report n_found/returned/fallback_level\n"
        "3. List structure_file paths if available\n"
    ),
    tools=[mcp_tools],
)


__all__ = [
    "BOHRIUM_EXECUTOR",
    "HTTPS_STORAGE",
    "mcp_tools",
    "root_agent",
]

