import os
import nest_asyncio
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
from dp.agent.adapter.adk import CalculationMCPToolset

# === 1. Environment & asyncio setup ===
load_dotenv()
nest_asyncio.apply()

# === Executors / Storage (same structure as OpenLAM, but named for Bohrium) ===
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
            "machine_type": ""
        }
    },
    "resources": {
        "envs": {}
    }
}

LOCAL_EXECUTOR = {"type": "local"}

HTTPS_STORAGE = {
    "type": "https",
    "plugin": {
        "type": "bohrium",
        "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
        "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
        "app_key": "agent"
    }
}

# === 2. Server URL from environment ===
server_url = os.getenv("SERVER_URL")

# === 3. Initialize MCP Toolset ===
mcp_tools = CalculationMCPToolset(
    connection_params=SseServerParams(url=server_url),
    storage=HTTPS_STORAGE,
    executor=LOCAL_EXECUTOR,
)

# === 4. Root LLM Agent ===
root_agent = LlmAgent(
    model=LiteLlm(model="deepseek/deepseek-chat"),
    name="Bohrium_Agent",
    description="Retrieves crystal structures from the Bohrium public database with filters for formula, elements, and physical properties.",
    instruction=(
        "You can call one MCP tool exposed by the Bohrium server:\n\n"

        "=== TOOL: fetch_bohrium_crystals ===\n"
        "Use this tool to query the Bohrium materials database.\n"
        "It supports filtering by:\n"
        "• formula (e.g., 'SiO2')\n"
        "• elements (list of element symbols, e.g., ['Na','Cl'])\n"
        "• match_mode (0=fuzzy, 1=exact)\n"
        "• space_symbol (space group, e.g., 'C2/m')\n"
        "• atom_count_range (e.g., ['1','100'])\n"
        "• predicted_formation_energy_range (eV, e.g., ['-10','10'])\n"
        "• band_gap_range (eV, e.g., ['0','5'])\n"
        "• n_results (max number of structures to return)\n"
        "• output_formats (list of 'json' or 'cif')\n\n"

        "=== EXAMPLES ===\n"
        "1) 查找含有Na和SiO3的结构：\n"
        "   → Tool: fetch_bohrium_crystals\n"
        "     formula: 'SiO3'\n"
        "     elements: ['Na']\n"
        "     match_mode: 0\n"

        "2) 查找三个带隙在 1–5 eV 的bcc的结构：\n"
        "   → Tool: fetch_bohrium_crystals\n"
        "     band_gap_range: ['1','5']\n"
        "     n_results: 3\n"

        "=== OUTPUT ===\n"
        "- The tool returns:\n"
        "   • output_dir: path to saved structures\n"
        "   • n_found: number of matching structures\n"
        "   • cleaned_structures: list of structure dicts\n\n"

        "=== NOTES ===\n"
        "- Use 'json' if the user wants metadata.\n"
        "- Use 'cif' for crystal visualization.\n"
        "- Filters are optional, but more filters yield more precise searches.\n\n"

        "=== ANSWER FORMAT ===\n"
        "1. Summarize the filters used\n"
        "2. Report the number of structures found\n"
        "3. Return the output directory path\n"
    ),
    tools=[mcp_tools],
)