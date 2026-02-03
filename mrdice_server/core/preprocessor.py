"""
Preprocessing module: intent recognition, parameter construction, and parameter correction.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .llm_client import LlmError, chat_json


SYSTEM_PROMPT_INTENT = (
    "You are a material database search assistant. "
    "Identify the material domain and type from the query. "
    "Return strict JSON only."
)

USER_PROMPT_INTENT_TEMPLATE = """\
Input Query: {query}

Return JSON:
{{
  "material_type": "crystal|mof|unknown",
  "domain": "semiconductor|catalyst|battery|perovskite|zeolite|other",
  "confidence": 0.0-1.0
}}
"""

SYSTEM_PROMPT_PARAMS = (
    "You are a material database search assistant. "
    "Extract and construct search parameters from the query. "
    "Return strict JSON only."
)

USER_PROMPT_PARAMS_TEMPLATE = """\
Input Query: {query}
Material Type: {material_type}
Domain: {domain}

Return JSON:
{{
  "expanded_query": "...",
  "filters": {{
    "formula": "...",
    "elements": ["..."],
    "space_group": 0,
    "band_gap": {{"min": 0.0, "max": 0.0}},
    "energy": {{"min": 0.0, "max": 0.0}},
    "time_range": {{"start": "...", "end": "..."}}
  }},
  "keywords": ["..."],
  "strictness": "strict|relaxed"
}}
"""

SYSTEM_PROMPT_CORRECT = (
    "You are a material database search assistant. "
    "Correct and validate search parameters. "
    "If parameters are invalid, provide corrected versions. "
    "Return strict JSON only."
)

USER_PROMPT_CORRECT_TEMPLATE = """\
Original Query: {query}
Current Parameters: {params}
Error Message: {error}

Return JSON:
{{
  "corrected": true|false,
  "reason": "...",
  "filters": {{
    "formula": "...",
    "elements": ["..."],
    "space_group": 0,
    "band_gap": {{"min": 0.0, "max": 0.0}},
    "energy": {{"min": 0.0, "max": 0.0}},
    "time_range": {{"start": "...", "end": "..."}}
  }},
  "keywords": ["..."]
}}
"""


def _strip_json(text: str) -> str:
    """Extract the first JSON object in the response."""
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text


def _safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON string."""
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_formula(query: str) -> Optional[str]:
    """Simple chemical formula heuristic: e.g., Fe2O3, LiFePO4."""
    match = re.search(r"\b([A-Z][a-z]?\d*){2,}\b", query)
    return match.group(0) if match else None


def _extract_elements(query: str) -> List[str]:
    """Heuristic: collect element symbols from capital letters."""
    elems = re.findall(r"[A-Z][a-z]?", query)
    seen = set()
    result = []
    for e in elems:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


def _elements_from_formula(formula: Optional[str]) -> List[str]:
    """Extract elements from formula."""
    if not formula:
        return []
    elems = re.findall(r"[A-Z][a-z]?", formula)
    seen = set()
    result = []
    for e in elems:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


def recognize_intent(query: str) -> Dict[str, Any]:
    """
    Recognize material domain and type from query.
    
    Returns:
        Dict with material_type, domain, confidence
    """
    user_prompt = USER_PROMPT_INTENT_TEMPLATE.format(query=query)
    try:
        raw = chat_json(SYSTEM_PROMPT_INTENT, user_prompt)
        if os.getenv("LLM_DEBUG") == "1":
            logging.info("LLM intent recognition output: %s", raw)
        json_text = _strip_json(raw)
        data = _safe_json_loads(json_text)
        if isinstance(data, dict):
            return {
                "material_type": data.get("material_type", "unknown"),
                "domain": data.get("domain", "other"),
                "confidence": data.get("confidence", 0.5),
            }
    except LlmError as e:
        logging.warning(f"LLM intent recognition failed: {e}")
    
    # Fallback heuristics
    lower = query.lower()
    if any(key in lower for key in ["mof", "pore", "surface area", "adsorbate", "孔", "比表面积"]):
        material_type = "mof"
        domain = "other"
    elif any(key in lower for key in ["perovskite", "钙钛矿"]):
        material_type = "crystal"
        domain = "perovskite"
    elif any(key in lower for key in ["battery", "电池", "lithium", "li"]):
        material_type = "crystal"
        domain = "battery"
    elif _extract_formula(query) or _extract_elements(query):
        material_type = "crystal"
        domain = "other"
    else:
        material_type = "unknown"
        domain = "other"
    
    return {
        "material_type": material_type,
        "domain": domain,
        "confidence": 0.3,
    }


def construct_parameters(query: str, material_type: str, domain: str) -> Dict[str, Any]:
    """
    Construct search parameters from query using LLM.
    
    Returns:
        Dict with expanded_query, filters, keywords, strictness
    """
    user_prompt = USER_PROMPT_PARAMS_TEMPLATE.format(
        query=query,
        material_type=material_type,
        domain=domain,
    )
    try:
        raw = chat_json(SYSTEM_PROMPT_PARAMS, user_prompt)
        if os.getenv("LLM_DEBUG") == "1":
            logging.info("LLM parameter construction output: %s", raw)
        json_text = _strip_json(raw)
        data = _safe_json_loads(json_text)
        if isinstance(data, dict):
            return {
                "expanded_query": data.get("expanded_query", query),
                "filters": data.get("filters", {}),
                "keywords": data.get("keywords", []),
                "strictness": data.get("strictness", "relaxed"),
            }
    except LlmError as e:
        logging.warning(f"LLM parameter construction failed: {e}")
    
    # Fallback heuristics
    formula = _extract_formula(query)
    elements = _extract_elements(query)
    if formula:
        elements = _elements_from_formula(formula)
    
    return {
        "expanded_query": query,
        "filters": {
            "formula": formula,
            "elements": elements,
            "space_group": None,
            "band_gap": {"min": None, "max": None},
            "energy": {"min": None, "max": None},
            "time_range": {"start": None, "end": None},
        },
        "keywords": [w for w in re.split(r"\s+", query) if w],
        "strictness": "relaxed",
    }


def correct_parameters(
    query: str,
    params: Dict[str, Any],
    error: str,
) -> Tuple[Dict[str, Any], bool, str]:
    """
    Correct parameters based on error message.
    
    Returns:
        Tuple of (corrected_params, was_corrected, reason)
    """
    user_prompt = USER_PROMPT_CORRECT_TEMPLATE.format(
        query=query,
        params=json.dumps(params, ensure_ascii=False),
        error=error,
    )
    try:
        raw = chat_json(SYSTEM_PROMPT_CORRECT, user_prompt)
        if os.getenv("LLM_DEBUG") == "1":
            logging.info("LLM parameter correction output: %s", raw)
        json_text = _strip_json(raw)
        data = _safe_json_loads(json_text)
        if isinstance(data, dict) and data.get("corrected"):
            return (
                {
                    "filters": data.get("filters", params.get("filters", {})),
                    "keywords": data.get("keywords", params.get("keywords", [])),
                },
                True,
                data.get("reason", "Parameters corrected by LLM"),
            )
    except LlmError as e:
        logging.warning(f"LLM parameter correction failed: {e}")
    
    # Fallback: return original params
    return params, False, "Correction not available"


def preprocess_query(query: str) -> Dict[str, Any]:
    """
    Complete preprocessing pipeline: intent recognition -> parameter construction.
    
    Returns:
        Dict with material_type, domain, filters, keywords, expanded_query, strictness
    """
    if not query or not query.strip():
        return {
            "material_type": "unknown",
            "domain": "other",
            "filters": {},
            "keywords": [],
            "expanded_query": "",
            "strictness": "relaxed",
        }
    
    # Step 1: Intent recognition
    intent = recognize_intent(query)
    material_type = intent["material_type"]
    domain = intent["domain"]
    
    # Step 2: Parameter construction
    params = construct_parameters(query, material_type, domain)
    
    return {
        "material_type": material_type,
        "domain": domain,
        "filters": params.get("filters", {}),
        "keywords": params.get("keywords", []),
        "expanded_query": params.get("expanded_query", query),
        "strictness": params.get("strictness", "relaxed"),
    }

