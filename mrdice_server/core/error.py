"""
Error management module.
"""
import logging
import traceback
from enum import Enum
from typing import Any, Dict, Optional


class ErrorType(Enum):
    """Error classification types."""
    NO_RESULTS = "no_results"
    INVALID_PARAMS = "invalid_params"
    LOGIC_ERROR = "logic_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


class MrDiceError(Exception):
    """Base exception for MrDice errors."""
    
    def __init__(self, message: str, error_type: ErrorType = ErrorType.UNKNOWN, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error_type": self.error_type.value,
            "message": str(self),
            "details": self.details,
        }


def classify_error(error: Exception) -> ErrorType:
    """
    Classify error type from exception.
    
    Args:
        error: Exception instance
    
    Returns:
        ErrorType enum value
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    
    if any(keyword in error_str for keyword in ["invalid", "validation", "parameter", "format"]):
        return ErrorType.INVALID_PARAMS
    
    if any(keyword in error_str for keyword in ["network", "connection", "timeout", "http", "request"]):
        return ErrorType.NETWORK_ERROR
    
    if any(keyword in error_str or keyword in error_type for keyword in ["logic", "index", "key", "attribute", "type"]):
        return ErrorType.LOGIC_ERROR
    
    return ErrorType.UNKNOWN


def log_error(
    error: Exception,
    logger: Optional[logging.Logger] = None,
    context: Optional[Dict[str, Any]] = None,
    level: str = "ERROR",
) -> Dict[str, Any]:
    """
    Log error with context and return error info.
    
    Args:
        error: Exception instance
        logger: Logger instance (if None, uses default)
        context: Additional context information
        level: Logging level
    
    Returns:
        Dictionary with error information
    """
    if logger is None:
        logger = logging.getLogger("mrdice")
    
    error_type = classify_error(error)
    error_info = {
        "error_type": error_type.value,
        "error_class": type(error).__name__,
        "message": str(error),
        "context": context or {},
    }
    
    # Log error
    log_method = getattr(logger, level.lower(), logger.error)
    log_method(
        f"[{error_type.value}] {type(error).__name__}: {error}",
        extra={"error_info": error_info, "context": context},
    )
    
    # Log traceback in debug mode
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
    
    return error_info


def handle_error(
    error: Exception,
    logger: Optional[logging.Logger] = None,
    context: Optional[Dict[str, Any]] = None,
    raise_again: bool = False,
) -> Dict[str, Any]:
    """
    Handle error: classify, log, and optionally re-raise.
    
    Args:
        error: Exception instance
        logger: Logger instance
        context: Additional context
        raise_again: Whether to re-raise the exception
    
    Returns:
        Error information dictionary
    
    Raises:
        The original exception if raise_again is True
    """
    error_info = log_error(error, logger, context)
    
    if raise_again:
        raise
    
    return error_info

