import logging
from typing import Any, Dict, List, Tuple

# Database descriptions for intelligent selection
DATABASE_DESCRIPTIONS = {
    "bohriumpublic": {
        "name": "Bohrium Public",
        "description": "Large-scale crystal structure database with formation energy and band gap data",
        "material_types": ["crystal"],
        "capabilities": ["formula", "elements", "space_group", "band_gap", "formation_energy"],
        "priority": 1,
    },
    "mofdb": {
        "name": "MOFdb",
        "description": "Metal-Organic Framework database with pore structure and surface area data",
        "material_types": ["mof"],
        "capabilities": ["formula", "elements", "pore_size", "surface_area"],
        "priority": 1,
    },
    "mofdbsql": {
        "name": "MOFdb SQL",
        "description": "MOF database with SQL query interface for complex searches",
        "material_types": ["mof"],
        "capabilities": ["formula", "elements", "sql_query"],
        "priority": 2,
    },
    "openlam": {
        "name": "OpenLAM",
        "description": "Open-source lattice matching database for crystal structures",
        "material_types": ["crystal"],
        "capabilities": ["formula", "elements", "lattice_parameters"],
        "priority": 2,
    },
    "optimade": {
        "name": "OPTIMADE",
        "description": "Multi-provider materials database with standardized API",
        "material_types": ["crystal", "mof"],
        "capabilities": ["formula", "elements", "space_group", "band_gap"],
        "priority": 3,
    },
}


def select_databases(
    material_type: str,
    domain: str,
    filters: Dict[str, Any],
) -> List[str]:
    """
    Intelligently select databases based on material type, domain, and required filters.
    
    Args:
        material_type: Type of material (crystal, mof, unknown)
        domain: Material domain (semiconductor, catalyst, battery, etc.)
        filters: Search filters to determine required capabilities
    
    Returns:
        List of database names in priority order
    """
    required_capabilities = set()
    if filters.get("formula"):
        required_capabilities.add("formula")
    if filters.get("elements"):
        required_capabilities.add("elements")
    if filters.get("space_group"):
        required_capabilities.add("space_group")
    if filters.get("band_gap"):
        required_capabilities.add("band_gap")
    if filters.get("energy"):
        required_capabilities.add("formation_energy")
    
    # Score databases based on compatibility
    scored: List[Tuple[int, str]] = []
    for db_name, db_info in DATABASE_DESCRIPTIONS.items():
        # Check material type compatibility
        if material_type != "unknown" and material_type not in db_info["material_types"]:
            continue
        
        # Calculate compatibility score
        score = 0
        db_caps = set(db_info["capabilities"])
        
        # Priority: higher priority = lower number, so we subtract
        score += (10 - db_info["priority"]) * 10
        
        # Capability match: each matching capability adds points
        matching_caps = required_capabilities & db_caps
        score += len(matching_caps) * 5
        
        # Domain-specific preferences
        if domain == "battery" and db_name == "bohriumpublic":
            score += 5
        if domain == "catalyst" and "mof" in db_name:
            score += 5
        
        scored.append((score, db_name))
    
    # Sort by score (descending) and return database names
    scored.sort(key=lambda x: x[0], reverse=True)
    result = [db_name for _, db_name in scored]
    
    # Fallback: if no databases selected, use default routes
    if not result:
        return plan_routes(material_type)
    
    logging.info(f"Selected databases for {material_type}/{domain}: {result}")
    return result


def plan_routes(material_type: str) -> List[str]:
    """
    Decide database route order based on material type (fallback method).
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
