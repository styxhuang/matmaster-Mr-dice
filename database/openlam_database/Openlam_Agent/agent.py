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
            "machine_type": ""
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
    name="OpenLAM_Agent",
    description="Retrieves crystal structures from the OpenLAM database with filters for formula, energy, and submission time.",
    instruction=(
        "You can call one MCP tool exposed by the OpenLAM server:\n\n"

        "=== TOOL: fetch_openlam_structures ===\n"
        "Use this tool to query the OpenLAM materials database.\n"
        "It supports filtering by:\n"
        "• formula (e.g., 'Fe2O3')\n"
        "• min_energy / max_energy (float, in eV)\n"
        "• min_submission_time / max_submission_time (ISO UTC string, e.g., '2024-01-01T00:00:00Z')\n"
        "• n_results (max number of results to return)\n"
        "• output_formats (list of 'json' or 'cif')\n\n"

        "=== EXAMPLES ===\n"
        "1) 查找 Fe2O3 材料结构：\n"
        "   → Tool: fetch_openlam_structures\n"
        "     formula: 'Fe2O3'\n"
        "     n_results: 5\n"
        "     output_formats: ['cif']\n\n"

        "2) 查找 2024 年之后上传的能量在 -10 到 20 eV 之间的材料：\n"
        "   → Tool: fetch_openlam_structures\n"
        "     min_energy: -10.0\n"
        "     max_energy: 20.0\n"
        "     min_submission_time: '2024-01-01T00:00:00Z'\n"
        "     output_formats: ['json']\n\n"

        "=== OUTPUT ===\n"
        "- The tool returns:\n"
        "   • output_dir: path to saved structures\n"
        "   • n_found: number of matching structures\n"
        "   • cleaned_structures: list of structure dicts\n\n"

        "=== NOTES ===\n"
        "- Use 'json' if the user asks for all metadata.\n"
        "- Use 'cif' for crystal visualization.\n"
        "- All filters are optional, but the more you provide, the more precise the search.\n\n"

        "=== ANSWER FORMAT ===\n"
        "1. Summarize the filters used\n"
        "2. Report the number of structures found\n"
        "3. Return the output directory path\n"
    ),
    tools=[mcp_tools],
)