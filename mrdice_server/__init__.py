"""MrDice Server - Unified materials database search server."""
from .core import mcp, structure_search_agent
from .core.config import (
    DEFAULT_MODEL,
    DEFAULT_N_RESULTS,
    DEFAULT_OUTPUT_FORMAT,
    MAX_N_RESULTS,
    get_bohrium_output_dir,
    get_data_dir,
    get_llm_config,
)

__all__ = [
    "structure_search_agent",
    "mcp",
    "DEFAULT_MODEL",
    "DEFAULT_N_RESULTS",
    "DEFAULT_OUTPUT_FORMAT",
    "MAX_N_RESULTS",
    "get_llm_config",
    "get_data_dir",
    "get_bohrium_output_dir",
]
