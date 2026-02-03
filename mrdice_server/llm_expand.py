import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .llm_client import chat_json, LlmError


SYSTEM_PROMPT = (
    "You are a material database search assistant. Return strict JSON only."
)

USER_PROMPT_TEMPLATE = """\
Input Query: {query}

Return JSON:
{{
  "expanded_query": "...",
  "material_type": "crystal|mof|unknown",
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


def _strip_json(text: str) -> str:
    """
    Extract the first JSON object in the response.
    """
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text


def _safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_formula(query: str) -> Optional[str]:
    # Simple chemical formula heuristic: e.g., Fe2O3, LiFePO4
    match = re.search(r"\b([A-Z][a-z]?\d*){2,}\b", query)
    return match.group(0) if match else None


def _extract_elements(query: str) -> List[str]:
    # Heuristic: collect element symbols from capital letters (works with Chinese text too)
    elems = re.findall(r"[A-Z][a-z]?", query)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for e in elems:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


def _elements_from_formula(formula: Optional[str]) -> List[str]:
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


def _fallback_expand(query: str) -> Dict[str, Any]:
    lower = query.lower()
    if any(key in lower for key in ["mof", "pore", "surface area", "adsorbate", "孔", "比表面积"]):
        material_type = "mof"
    else:
        material_type = "crystal" if _extract_formula(query) or _extract_elements(query) else "unknown"

    formula = _extract_formula(query)
    elements = _extract_elements(query)
    if formula:
        # Prefer elements parsed from formula for precision
        elements = _elements_from_formula(formula)

    return {
        "expanded_query": query,
        "material_type": material_type,
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
        "fallback": True,
    }


def expand_query(query: str) -> Dict[str, Any]:
    """
    Use LLM to expand + classify the query. Falls back to heuristics on failure.
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(query=query)
    try:
        raw = chat_json(SYSTEM_PROMPT, user_prompt)
        if os.getenv("LLM_DEBUG") == "1":
            logging.info("LLM raw output: %s", raw)
        json_text = _strip_json(raw)
        data = _safe_json_loads(json_text)
        if not isinstance(data, dict):
            if os.getenv("LLM_DEBUG") == "1":
                logging.warning("LLM JSON parse failed, using fallback. Raw: %s", raw)
            return _fallback_expand(query)
        data["fallback"] = False
        return data
    except LlmError:
        return _fallback_expand(query)
