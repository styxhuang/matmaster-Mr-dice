"""Core module: server, configuration, LLM, preprocessing, and postprocessing."""
from .config import (
    DEFAULT_MODEL,
    DEFAULT_N_RESULTS,
    DEFAULT_OUTPUT_FORMAT,
    LOCAL_EXECUTOR,
    MAX_N_RESULTS,
    get_bohrium_output_dir,
    get_data_dir,
    get_llm_config,
)
from .error import ErrorType, MrDiceError, classify_error, handle_error, log_error
from .logger import get_logger, setup_logger
from .llm_client import LlmError, chat_json
from .postprocessor import (
    DegradationRecord,
    degrade_filters,
    handle_search_error,
    should_retry_with_correction,
)
from .preprocessor import (
    construct_parameters,
    correct_parameters,
    preprocess_query,
    recognize_intent,
)
from .server import mcp, fetch_structures_from_db

__all__ = [
    # Server
    "fetch_structures_from_db",
    "mcp",
    # Config
    "DEFAULT_MODEL",
    "DEFAULT_N_RESULTS",
    "DEFAULT_OUTPUT_FORMAT",
    "LOCAL_EXECUTOR",
    "MAX_N_RESULTS",
    "get_llm_config",
    "get_data_dir",
    "get_bohrium_output_dir",
    # LLM
    "LlmError",
    "chat_json",
    "recognize_intent",
    "construct_parameters",
    "correct_parameters",
    "preprocess_query",
    # Postprocessing
    "DegradationRecord",
    "degrade_filters",
    "handle_search_error",
    "should_retry_with_correction",
    # Error handling
    "ErrorType",
    "MrDiceError",
    "classify_error",
    "handle_error",
    "log_error",
    # Logging
    "setup_logger",
    "get_logger",
]
