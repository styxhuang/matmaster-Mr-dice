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
    "For filters.formula: use a single chemical formula string without hyphens (e.g. Fe2O3, LiFePO4, TiAlO3). "
    "Do NOT use element-element style (e.g. Ti-Al-O is invalid); put elements in elements array if listing only. "
    "Important: filters.elements means 'structure must contain ALL listed elements'. "
    "So for '过渡金属硫化物' or '某类金属硫化物', the user means 'contains S and (at least one transition metal)'. "
    "Use elements_options: list of representative pairs so we search each and merge, e.g. elements_options: [[\"S\",\"Ti\"], [\"S\",\"V\"], [\"S\",\"Mo\"], [\"S\",\"Fe\"], [\"S\",\"Co\"]]. "
    "Leave elements empty when elements_options is set. Same for '稀土氧化物': elements_options: [[\"La\",\"O\"], [\"Ce\",\"O\"], [\"Nd\",\"O\"]]. "
    "Limit to 6–8 options to cover variety without too many queries. "
    "Only set band_gap or energy when the user explicitly mentions band gap or formation energy constraints; "
    "otherwise set them to null. Only set space_group when the user explicitly mentions space group; otherwise 0 or null. "
    "Decide whether the user clearly prefers one specific database "
    "(among: bohriumpublic, mofdbsql, openlam, optimade). If no clear preference, leave prefer_db empty. "
    "When the query involves comparing data across different databases (e.g. 对比不同数据库中, 比较...库), set prefer_db to a list of those database names (e.g. [\"mofdbsql\", \"optimade\"]) so we fetch from each in parallel and return by source—do not use a single prefer_db. "
    "When the query involves MOF (and is not a cross-DB comparison), use the mofs table for sql_query and set prefer_db to mofdbsql. "
    "For MOFdb (mofdbsql): output filters.sql_query only with columns that exist. "
    "Never add WHERE mofs.database = '...' (e.g. 'HMOF') in sql_query—even if the user query mentions HMOF or a dataset name; backend is a single mof_database.db. "
    "Table mofs has exactly these columns only: id, name, database, cif_path, n_atom, lcd, pld, url, hashkey, mofid, mofkey, pxrd, void_fraction, surface_area_m2g, surface_area_m2cm3, pore_size_distribution, batch_number. "
    "mofs has NO: topology, coordination_number, framework_dimensionality, co2_adsorption_mmolg, or any adsorption column (adsorption is in other tables). "
    "Table elements: mof_id, element_symbol, n_atom; JOIN mofs ON mofs.id = elements.mof_id for element filter. "
    "If the user asks for topology, coordination, framework dimension, CO2/adsorption, or adsorption selectivity (e.g. CH4/N2), mofs does not have those; use a SELECT with only the columns above (e.g. database, surface_area_m2g, void_fraction); do not add selectivity to SQL—it requires post-processing. "
    "SQL must SELECT at least id, name, database, cif_path. Do not include LIMIT. Return strict JSON only."
)

USER_PROMPT_PARAMS_TEMPLATE = """\
Input Query: {query}
Material Type: {material_type}
Domain: {domain}

Return JSON:
{{
  "expanded_query": "...",
  "filters": {{
    "formula": "or null",
    "elements": "single set when exact composition, else leave []",
    "elements_options": "when user says X类Y化物: list of 6-8 pairs",
    "sql_query": "MOF: SELECT from mofs (id, name, cif_path, n_atom, lcd, pld, void_fraction, surface_area_m2g, ...); never WHERE mofs.database=...; no topology/co2_adsorption; elements via JOIN (no LIMIT)",
    "space_group": 0 or null,
    "band_gap": null,
    "energy": null,
    "time_range": {{"start": "", "end": ""}}
  }},
  "keywords": ["..."],
  "strictness": "strict|relaxed",
  "prefer_db": "single: bohriumpublic|mofdbsql|openlam|optimade; or list for compare: [\"mofdbsql\", \"optimade\"]"
}}
Rules: (1) 过渡金属硫化物 etc. -> elements_options (6-8 pairs). (2) band_gap/energy null unless user asks. (3) MOF: sql_query from mofs only; never put WHERE mofs.database = '...' in SQL (ignore HMOF/dataset name in query). (4) 对比/比较不同数据库: prefer_db as list of DBs to query in parallel, not single DB.
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
    "formula": "or null",
    "elements": ["..."],
    "sql_query": "SELECT ... for MOFdb when applicable, or null",
    "space_group": 0 or null,
    "band_gap": null,
    "energy": null,
    "time_range": {{"start": "", "end": ""}}
  }},
  "keywords": ["..."]
}}
Use null for band_gap and energy unless the user explicitly requested those filters.
"""


# === Relax to element-only filter (when no results) ===

SYSTEM_PROMPT_RELAX_ELEMENTS = (
    "You are a material database search assistant. "
    "The first search returned zero results because the query used vague terms (e.g. '稀土', '过渡金属') "
    "that databases do not understand. Your task: output a new search that uses ONLY chemical element symbols. "
    "Rules: (1) Expand categories to concrete elements: e.g. 稀土 -> La,Ce,Pr,Nd,Pm,Sm,Eu,Gd,Tb,Dy,Ho,Er,Tm,Yb,Lu (or a subset); "
    "过渡金属(排除Fe/Ni) -> e.g. Ti,V,Cr,Mn,Zr,Nb,Mo,Tc,Ru,Rh,Pd,etc.; (2) 氧 -> O; (3) For '三元' (ternary), "
    "output exactly 3 elements in the elements array (e.g. one rare-earth + one transition metal + O). "
    "Output a single representative elements list that matches the user intent. "
    "Leave formula empty, space_group 0, band_gap/energy empty. Return strict JSON only."
)

USER_PROMPT_RELAX_ELEMENTS_TEMPLATE = """\
Original query: {query}
Previous filters (returned 0 results): {params}

Return a relaxed search using ONLY element symbols.

Return JSON:
{{
  "filters": {{
    "formula": "",
    "elements": ["La", "Ti", "O"],
    "space_group": 0,
    "band_gap": {{"min": 0.0, "max": 0.0}},
    "energy": {{"min": 0.0, "max": 0.0}},
    "time_range": {{"start": "", "end": ""}}
  }},
  "expanded_query": "short description of the relaxed condition in one line"
}}
"""


__all__ = [
    "SYSTEM_PROMPT_INTENT",
    "USER_PROMPT_INTENT_TEMPLATE",
    "SYSTEM_PROMPT_PARAMS",
    "USER_PROMPT_PARAMS_TEMPLATE",
    "SYSTEM_PROMPT_CORRECT",
    "USER_PROMPT_CORRECT_TEMPLATE",
    "SYSTEM_PROMPT_RELAX_ELEMENTS",
    "USER_PROMPT_RELAX_ELEMENTS_TEMPLATE",
]


