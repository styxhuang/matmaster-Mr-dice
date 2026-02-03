import os
from pathlib import Path


DEFAULT_MODEL = "deepseek/deepseek-chat"
DEFAULT_N_RESULTS = 5
MAX_N_RESULTS = 20
DEFAULT_OUTPUT_FORMAT = "cif"


def get_llm_config() -> dict:
    """
    LLM config is read from environment variables to avoid hardcoding secrets.
    - LLM_PROVIDER: "deepseek" | "openai" | "custom"
    - LLM_MODEL: model name, e.g. "deepseek/deepseek-chat"
    - LLM_API_BASE: optional base URL override
    - LLM_API_KEY: secret key (must be set in env, never hardcode)
    """
    return {
        "provider": os.getenv("LLM_PROVIDER", "deepseek"),
        "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
        "api_base": os.getenv("LLM_API_BASE", "").strip() or None,
        "api_key": os.getenv("LLM_API_KEY", "").strip() or None,
    }


def get_data_dir() -> Path:
    """
    Get the base data directory from environment variable.
    Defaults to current working directory if not set.
    - MR_DICE_DATA_DIR: base directory for storing materials data
    """
    data_dir = os.getenv("MR_DICE_DATA_DIR", "")
    if data_dir:
        return Path(data_dir)
    # Fallback to project root
    return Path(__file__).parent.parent


def get_bohrium_output_dir() -> Path:
    """
    Get the output directory for Bohrium public database results.
    - MR_DICE_BOHRIUM_OUTPUT_DIR: specific output directory for Bohrium data
    If not set, uses MR_DICE_DATA_DIR/database/bohriumpublic_database/Bohriumpublic_Server/materials_data_bohriumpublic
    """
    output_dir = os.getenv("MR_DICE_BOHRIUM_OUTPUT_DIR", "")
    if output_dir:
        return Path(output_dir)
    # Default relative path from data directory
    return get_data_dir() / "database" / "bohriumpublic_database" / "Bohriumpublic_Server" / "materials_data_bohriumpublic"
