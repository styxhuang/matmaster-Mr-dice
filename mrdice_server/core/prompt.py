"""
Centralized LLM prompts and templates for MrDice.
"""

# === Intent recognition ===

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


# === Parameter construction ===

SYSTEM_PROMPT_PARAMS = (
    "You are a material database search assistant. "
    "Extract and construct search parameters from the query. "
    "Decide whether the user clearly prefers one specific database "
    "(among: bohriumpublic, mofdbsql, openlam, optimade). "
    "If there is no clear preference, leave prefer_db empty. "
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
  "strictness": "strict|relaxed",
  "prefer_db": "bohriumpublic|mofdbsql|openlam|optimade|"
}}
"""


# === Parameter correction ===

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


__all__ = [
    "SYSTEM_PROMPT_INTENT",
    "USER_PROMPT_INTENT_TEMPLATE",
    "SYSTEM_PROMPT_PARAMS",
    "USER_PROMPT_PARAMS_TEMPLATE",
    "SYSTEM_PROMPT_CORRECT",
    "USER_PROMPT_CORRECT_TEMPLATE",
]


