"""
Postprocessing module: error classification, parameter correction retry, and degradation logging.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from .error import ErrorType, classify_error as _classify_error
from .preprocessor import correct_parameters
from ..models.schema import SearchResult


class DegradationRecord:
    """Record of degradation attempts and results."""
    
    def __init__(self):
        self.attempts: List[Dict[str, Any]] = []
    
    def add_attempt(
        self,
        attempt: int,
        filters: Dict[str, Any],
        databases: List[str],
        results_count: int,
        error: Optional[str] = None,
    ):
        """Record a degradation attempt."""
        self.attempts.append({
            "attempt": attempt,
            "filters": filters,
            "databases": databases,
            "results_count": results_count,
            "error": error,
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "total_attempts": len(self.attempts),
            "attempts": self.attempts,
        }


def classify_error(error: Exception, results: List[SearchResult]) -> Tuple[ErrorType, str]:
    """
    Classify error type and provide error message.
    
    Returns:
        Tuple of (error_type, error_message)
    """
    if not results:
        return ErrorType.NO_RESULTS, "No results found"
    
    error_type = _classify_error(error)
    error_msg = str(error)
    
    return error_type, error_msg


def should_retry_with_correction(error_type: ErrorType) -> bool:
    """
    Determine if we should retry with parameter correction.
    
    Returns:
        True if parameter correction might help
    """
    return error_type in [ErrorType.INVALID_PARAMS, ErrorType.NO_RESULTS]


def degrade_filters(filters: Dict[str, Any], attempt: int) -> Dict[str, Any]:
    """
    Degrade filters for retry attempts.
    
    attempt 1: strict (all filters)
    attempt 2: remove band_gap, space_group, time_range
    attempt 3: keep only elements or keywords-friendly filters
    attempt 4+: minimal filters (only elements if available, otherwise empty)
    """
    f = dict(filters or {})
    
    if attempt == 1:
        return f
    
    if attempt == 2:
        # Remove strict filters
        f["band_gap"] = {"min": None, "max": None}
        f["space_group"] = None
        f["time_range"] = {"start": None, "end": None}
        return f
    
    if attempt == 3:
        # Keep only basic filters
        keep = {"elements", "formula"}
        return {k: v for k, v in f.items() if k in keep}
    
    # attempt 4+: minimal
    if f.get("elements"):
        return {"elements": f["elements"]}
    if f.get("formula"):
        return {"formula": f["formula"]}
    
    return {}


def handle_search_error(
    query: str,
    params: Dict[str, Any],
    error: Exception,
    results: List[SearchResult],
    degradation_record: DegradationRecord,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Handle search errors: classify, correct parameters if needed, and decide retry.
    
    Returns:
        Tuple of (corrected_params_or_none, should_retry)
    """
    error_type, error_msg = classify_error(error, results)
    logging.warning(f"Search error [{error_type.value}]: {error_msg}")
    
    if not should_retry_with_correction(error_type):
        # For logic/network errors, don't retry with correction
        return None, False
    
    # Try parameter correction for invalid params or no results
    if error_type == ErrorType.INVALID_PARAMS:
        corrected_params, was_corrected, reason = correct_parameters(
            query,
            params,
            error_msg,
        )
        if was_corrected:
            logging.info(f"Parameters corrected: {reason}")
            degradation_record.add_attempt(
                attempt=0,  # Special attempt for correction
                filters=corrected_params.get("filters", {}),
                databases=[],
                results_count=0,
                error=f"Correction: {reason}",
            )
            return corrected_params, True
    
    # For no results, we'll use degradation strategy
    if error_type == ErrorType.NO_RESULTS:
        return None, True  # Will use degradation in main loop
    
    return None, False

