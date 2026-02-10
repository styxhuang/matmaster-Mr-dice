"""
Preprocessing module: intent recognition, parameter construction, and parameter correction.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .llm_client import LlmError, chat_json
from .prompt import (
    SYSTEM_PROMPT_CORRECT,
    SYSTEM_PROMPT_INTENT,
    SYSTEM_PROMPT_PARAMS,
    SYSTEM_PROMPT_RELAX_ELEMENTS,
    USER_PROMPT_CORRECT_TEMPLATE,
    USER_PROMPT_INTENT_TEMPLATE,
    USER_PROMPT_PARAMS_TEMPLATE,
    USER_PROMPT_RELAX_ELEMENTS_TEMPLATE,
)


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


def _detect_target_databases(query: str) -> List[str]:
    """Detect explicitly requested databases from query text."""
    if not query:
        return []
    lower = query.lower()
    targets: List[str] = []

    def _add(db_name: str) -> None:
        if db_name not in targets:
            targets.append(db_name)

    if "bohriumpublic" in lower or "bohrium public" in lower or "bohrium 公共" in lower:
        _add("bohriumpublic")
    if "mofdb" in lower or "mof db" in lower:
        _add("mofdbsql")
    # MOF-related named databases that should map to MOFdb SQL
    if "coremof" in lower or "core mof" in lower:
        _add("mofdbsql")
    if "hmof" in lower or "h mof" in lower:
        _add("mofdbsql")
    if "mof数据库" in query or "mof 数据库" in query:
        _add("mofdbsql")
    if "openlam" in lower or "open lam" in lower:
        _add("openlam")
    if "optimade" in lower:
        _add("optimade")

    directional_markers = ["只用", "只使用", "仅用", "仅使用", "only use", "use only"]
    has_directional_hint = any(marker in lower for marker in directional_markers)

    if has_directional_hint:
        if "mof" in lower and "mofdb" not in lower and "mof db" not in lower:
            _add("mofdbsql")
        if "bohrium" in lower and "bohriumpublic" not in lower:
            _add("bohriumpublic")
        if "openlam" not in lower and "open lam" not in lower and "open" in lower and "lam" in lower:
            _add("openlam")

    return targets


def _wants_band_gap(query: str) -> bool:
    """
    Heuristic: user explicitly asks for band gap values (not just filtering).
    Used to set a sensible default range so we avoid returning many N/A gaps.
    """
    if not query:
        return False
    lower = query.lower()
    return (
        ("band gap" in lower)
        or ("bandgap" in lower)
        or ("带隙" in query)
        or ("禁带" in query)
        or ("能隙" in query)
    )


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
        Dict with expanded_query, filters, keywords, strictness, prefer_db
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
                "prefer_db": data.get("prefer_db", ""),
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
        "prefer_db": "",
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


def relax_to_element_only_filter(
    query: str,
    original_filters: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    When the first search returns no results, use LLM to build a relaxed filter
    that uses only element symbols (e.g. expand 稀土/过渡金属 to concrete elements).

    Returns:
        Tuple of (new_filters, expanded_query) or (None, None) on failure.
    """
    user_prompt = USER_PROMPT_RELAX_ELEMENTS_TEMPLATE.format(
        query=query,
        params=json.dumps(original_filters, ensure_ascii=False),
    )
    try:
        raw = chat_json(SYSTEM_PROMPT_RELAX_ELEMENTS, user_prompt, timeout=25)
        if os.getenv("LLM_DEBUG") == "1":
            logging.info("LLM relax-elements output: %s", raw)
        json_text = _strip_json(raw)
        data = _safe_json_loads(json_text)
        if not isinstance(data, dict):
            return None, None
        filters = data.get("filters")
        if not isinstance(filters, dict):
            return None, None
        elements = filters.get("elements")
        if not elements or not isinstance(elements, list):
            return None, None
        # Ensure only valid element-like strings
        elements = [str(x).strip() for x in elements if str(x).strip()]
        if not elements:
            return None, None
        # Build clean element-only filters (no formula, neutral space_group/band_gap/energy)
        new_filters = {
            "formula": "",
            "elements": elements,
            "space_group": 0,
            "band_gap": {"min": 0.0, "max": 0.0},
            "energy": {"min": 0.0, "max": 0.0},
            "time_range": {"start": "", "end": ""},
        }
        expanded = (data.get("expanded_query") or "").strip() or None
        return new_filters, expanded
    except LlmError as e:
        logging.warning("LLM relax-to-elements failed: %s", e)
        return None, None


def preprocess_query(query: str) -> Dict[str, Any]:
    """
    Complete preprocessing pipeline: intent recognition -> parameter construction.
    
    Returns:
        Dict with material_type, domain, filters, keywords, expanded_query, strictness, target_databases
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
    filters = params.get("filters", {}) or {}

    # Prefer database decided by LLM when available; otherwise fall back to heuristics.
    target_databases: List[str] = []
    prefer_db = params.get("prefer_db")
    if isinstance(prefer_db, str):
        prefer_db = prefer_db.strip()
        if prefer_db:
            target_databases = [prefer_db]
    elif isinstance(prefer_db, list):
        cleaned = [str(x).strip() for x in prefer_db if str(x).strip()]
        if cleaned:
            target_databases = cleaned
    if not target_databases:
        target_databases = _detect_target_databases(query)

    # If user explicitly mentions a MOF sub-database (e.g. CoREMOF 2019, hMOF),
    # add a database filter and ensure we only hit MOFdb—unless this is a
    # cross-database comparison (multiple target_databases), then keep all.
    lower = query.lower()
    if len(target_databases) <= 1:
        if "coremof 2019" in lower:
            filters = dict(filters)
            filters["database"] = "CoREMOF 2019"
            target_databases = ["mofdbsql"]
        elif "coremof 2014" in lower:
            filters = dict(filters)
            filters["database"] = "CoREMOF 2014"
            target_databases = ["mofdbsql"]
        elif "coremof" in lower or "core mof" in lower:
            filters = dict(filters)
            filters["database"] = "CoREMOF"
            target_databases = ["mofdbsql"]
        elif "hmof" in lower or "h mof" in lower:
            filters = dict(filters)
            filters["database"] = "hMOF"
            target_databases = ["mofdbsql"]

    # If the user explicitly asked for band gap values but didn't provide a numeric
    # range, set a tiny positive default min to reduce "N/A" band gap entries.
    # Do NOT apply to MOF-only intents.
    if material_type != "mof" and _wants_band_gap(query):
        bg = filters.get("band_gap")
        if bg is None:
            filters = dict(filters)
            filters["band_gap"] = {"min": 0.01, "max": None}
        elif isinstance(bg, dict):
            bg_min = bg.get("min")
            bg_max = bg.get("max")
            # Only fill defaults when both ends are effectively unspecified.
            if (bg_min is None or bg_min == "") and (bg_max is None or bg_max == ""):
                new_bg = dict(bg)
                new_bg["min"] = 0.01
                new_bg["max"] = None
                filters = dict(filters)
                filters["band_gap"] = new_bg

    return {
        "material_type": material_type,
        "domain": domain,
        "filters": filters,
        "keywords": params.get("keywords", []),
        "expanded_query": params.get("expanded_query", query),
        "strictness": params.get("strictness", "relaxed"),
        "target_databases": target_databases,
    }

