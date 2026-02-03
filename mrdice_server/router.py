from typing import Any, Dict, List, Tuple


def plan_routes(material_type: str) -> List[str]:
    """
    Decide database route order based on material type.
    """
    if material_type == "mof":
        return ["mofdb", "mofdbsql"]
    if material_type == "crystal":
        return ["bohriumpublic", "openlam", "optimade"]
    return ["bohriumpublic", "openlam", "optimade", "mofdb", "mofdbsql"]


def degrade_filters(filters: Dict[str, Any], attempt: int) -> Dict[str, Any]:
    """
    attempt 1: strict (all filters)
    attempt 2: remove band_gap, space_group, time_range
    attempt 3: keep only elements or keywords-friendly filters
    """
    f = dict(filters or {})
    if attempt == 1:
        return f
    if attempt == 2:
        f["band_gap"] = {"min": None, "max": None}
        f["space_group"] = None
        f["time_range"] = {"start": None, "end": None}
        return f
    # attempt 3
    keep = {"elements", "formula"}
    return {k: v for k, v in f.items() if k in keep}


def normalize_n_results(n_results: int, default_n: int, max_n: int) -> int:
    if not n_results or n_results <= 0:
        return default_n
    return min(n_results, max_n)
