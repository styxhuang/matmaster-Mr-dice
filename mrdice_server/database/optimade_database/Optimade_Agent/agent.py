import os
import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from typing import Any, Dict

from pathlib import Path
from typing import Any, Dict

import nest_asyncio
from dotenv import load_dotenv
from dp.agent.adapter.adk import CalculationMCPToolset
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types


load_dotenv()
nest_asyncio.apply()

# Set environment variables if needed
# Global Configuration
# BOHRIUM_EXECUTOR = {
#     "type": "dispatcher",
#     "machine": {
#         "batch_type": "Bohrium",
#         "context_type": "Bohrium",
#         "remote_profile": {
#             "email": os.getenv("BOHRIUM_EMAIL"),
#             "password": os.getenv("BOHRIUM_PASSWORD"),
#             "program_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
#             "input_data": {
#                 "image_name": "registry.dp.tech/dptech/dp/native/prod-19853/dpa-mcp:0.0.0",
#                 "job_type": "container",
#                 "platform": "ali",
#                 "scass_type": "1 * NVIDIA V100_32g"
#             }
#         }
#     }
# }

BOHRIUM_EXECUTOR = {
    "type": "dispatcher",
    "machine": {
        "batch_type": "OpenAPI",
        "context_type": "OpenAPI",
        "remote_profile": {
            "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
            "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
            "app_key": "agent",
            "image_address": "registry.dp.tech/dptech/dp/native/prod-19853/dpa-mcp:0.0.0",
            "platform": "ali",
            "machine_type": "c8_m31_1 * NVIDIA T4"
        }
    },
    "resources": {
        "envs": {}
    }
}

LOCAL_EXECUTOR = {
    "type": "local"
}
BOHRIUM_STORAGE = {
    "type": "bohrium",
    "username": os.getenv("BOHRIUM_EMAIL"),
    "password": os.getenv("BOHRIUM_PASSWORD"),
    "project_id": int(os.getenv("BOHRIUM_PROJECT_ID"))
}

HTTPS_STORAGE = {
  "type": "https",
  "plugin": {
    "type": "bohrium",
    "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
    "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
    "app_key": "agent"
  }
}

server_url = os.getenv("SERVER_URL")


# Initialize MCP tools and agent
mcp_tools = CalculationMCPToolset(
    connection_params=SseServerParams(url=server_url),
    storage=HTTPS_STORAGE,
    executor=LOCAL_EXECUTOR,
)


root_agent = LlmAgent(
    model=LiteLlm(model="deepseek/deepseek-chat"),
    name="Optimade_Agent",
    description=(
        "Retrieves crystal structures from OPTIMADE databases using raw filters, "
        "with optional provider-specific helpers for space group and band gap."
    ),
    instruction=(
        "You can call three MCP tools exposed by the server:\n"
        "1) fetch_structures_with_filter(filter, as_format='cif'|'json', n_results=2, providers=[...])\n"
        "   - Sends ONE raw OPTIMADE filter string to all chosen providers at once.\n"
        "2) fetch_structures_with_spg(base_filter, spg_number, as_format='cif'|'json', n_results=3, providers=[...])\n"
        "   - Adds provider-specific *space-group* clauses (e.g., _tcod_sg, _oqmd_spacegroup, _alexandria_space_group) and queries providers in parallel.\n"
        "3) fetch_structures_with_bandgap(base_filter, min_bg=None, max_bg=None, as_format='cif'|'json', n_results=2, providers=[...])\n"
        "   - Adds provider-specific *band-gap* clauses (e.g., _oqmd_band_gap, _gnome_bandgap, _mcloudarchive_band_gap) and queries in parallel.\n\n"
        "   - For band-gap related tasks, **use 'json' as the default as_format** to include complete metadata.\n\n"

        "=== DEFAULT PROVIDERS ===\n"
        "- Raw filter: alexandria, cmr, cod, mcloud, mcloudarchive, mp, mpdd, mpds, nmd, odbx, omdb, oqmd, tcod, twodmatpedia\n"
        "- Space group (SPG): alexandria, cod, mpdd, nmd, odbx, oqmd, tcod\n"
        "- Band gap (BG): alexandria, odbx, oqmd, mcloudarchive, twodmatpedia\n\n"

        "=== OPTIMADE FILTER QUICK GUIDE ===\n"
        "• Equality: chemical_formula_reduced=\"O2Si\"\n"
        "• Substring: chemical_formula_descriptive CONTAINS \"H2O\"\n"
        "• Lists: elements HAS ALL \"Al\",\"O\",\"Mg\" | HAS ANY | HAS ONLY\n"
        "• Numbers: nelements=3, nelements>=2 AND nelements<=7\n"
        "• Logic: AND, OR, NOT (use parentheses)\n"
        "Tip: exact element set → elements HAS ALL \"A\",\"B\" AND nelements=2\n\n"

        "=== HOW TO CHOOSE A TOOL ===\n"
        "- Pure element/formula/logic → use fetch_structures_with_filter.\n"
        "- Needs a specific space group number (1–230) → use fetch_structures_with_spg with base_filter.\n"
        "- Needs band-gap range → use fetch_structures_with_bandgap with base_filter and min/max.\n\n"

        "=== DEMOS (用户问题 → 工具与参数) ===\n"
        "1) 用户：找3个包含si o， 且含有四种元素的，不能同时含有铁铝，的材料，从alexandria, cmr, nmd，oqmd，omdb中查找。\n"
        "   → Tool: fetch_structures_with_filter\n"
        "     filter: elements HAS ALL \"Si\",\"O\" AND nelements=4 AND NOT (elements HAS ALL \"Fe\",\"Al\")\n"
        "     as_format: \"cif\"\n"
        "     n_results: 3\n"
        "     providers: [\"alexandria\",\"cmr\",\"nmd\",\"oqmd\",\"omdb\"]\n\n"

        "2) 用户：找到一些A2b3C4的材料，不能含有 Fe，F，CI，H元素，要含有铝或者镁或者钠，我要全部信息。\n"
        "   → Tool: fetch_structures_with_filter\n"
        "     filter: chemical_formula_anonymous=\"A2B3C4\" AND NOT (elements HAS ANY \"Fe\",\"F\",\"Cl\",\"H\") AND (elements HAS ANY \"Al\",\"Mg\",\"Na\")\n"
        "     as_format: \"json\"  # “全部信息”\n"

        "3) 用户：找一些ZrO，从mpds, cmr, alexandria, omdb, odbx里面找\n"
        "   → Tool: fetch_structures_with_filter\n"
        "     filter: chemical_formula_reduced=\"OZr\"  # 注意元素要按字母表顺序\n"
        "     as_format: \"cif\"\n"
        "     providers: [\"mpds\",\"cmr\",\"alexandria\",\"omdb\",\"odbx\"]\n\n"

        "4) 用户：查找一个gamma相的TiAl合金\n"
        "   → Tool: fetch_structures_with_spg\n"
        "     base_filter: elements HAS ONLY \"Ti\",\"Al\"\n"
        "     spg_number: 123   # γ‑TiAl (L1₀) 常记作 P4/mmm，为 123空间群；你需要根据相结构信息确定空间群序号\n"
        "     as_format: \"cif\"\n"
        "     n_results: 1\n"

        "5) 用户：找一些含铝的，能带在1.0-2.0间的材料\n"
        "   → Tool: fetch_structures_with_bandgap\n"
        "     base_filter: elements HAS ALL \"Al\"\n"
        "     min_bg: 1.0\n"
        "     max_bg: 2.0\n"
        "     as_format: \"json\"\n     # 默认输出json格式，对于能带相关查询"   

        "=== ANSWER STYLE ===\n"
        "- Briefly explain the applied constraints (elements/formula + SPG/BG if any).\n"
        "- Provide the archive/folder path.\n"
    ),
    tools=[mcp_tools],
)