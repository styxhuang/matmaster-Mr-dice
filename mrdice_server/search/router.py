"""
Router module: intelligent database selection based on query characteristics.
"""
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Import database constants
_project_root = Path(__file__).parent.parent
_database_path = _project_root / "database"
if str(_database_path) not in sys.path:
    sys.path.insert(0, str(_database_path))

# Load database info from constants
DATABASE_DESCRIPTIONS: Dict[str, Dict[str, Any]] = {}

try:
    from bohriumpublic_database.constant import DATABASE_INFO as bohrium_info
    DATABASE_DESCRIPTIONS["bohriumpublic"] = bohrium_info
except ImportError as e:
    logging.warning(f"Failed to import bohriumpublic constants: {e}")

try:
    from mofdbsql_database.constant import DATABASE_INFO as mofdbsql_info
    DATABASE_DESCRIPTIONS["mofdbsql"] = mofdbsql_info
except ImportError as e:
    logging.warning(f"Failed to import mofdbsql constants: {e}")

try:
    from openlam_database.constant import DATABASE_INFO as openlam_info
    DATABASE_DESCRIPTIONS["openlam"] = openlam_info
except ImportError as e:
    logging.warning(f"Failed to import openlam constants: {e}")

try:
    from optimade_database.constant import DATABASE_INFO as optimade_info
    DATABASE_DESCRIPTIONS["optimade"] = optimade_info
except ImportError as e:
    logging.warning(f"Failed to import optimade constants: {e}")

# Fallback descriptions if constants not available
if not DATABASE_DESCRIPTIONS:
    DATABASE_DESCRIPTIONS = {
        "bohriumpublic": {
            "name": "Bohrium Public",
            "description": "Large-scale crystal structure database with formation energy and band gap data",
            "material_types": ["crystal"],
            "capabilities": ["formula", "elements", "space_group", "band_gap", "formation_energy"],
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
        material_type: Material type (crystal, mof, unknown)
        domain: Material domain (semiconductor, catalyst, battery, etc.)
        filters: Search filters dictionary
    
    Returns:
        List of database names in priority order
    """
    if not DATABASE_DESCRIPTIONS:
        # Fallback to default routes
        return plan_routes(material_type, domain)
    
    # Score databases based on compatibility
    db_scores: Dict[str, float] = {}
    
    for db_name, db_info in DATABASE_DESCRIPTIONS.items():
        score = 0.0
        
        # Material type match
        if material_type in db_info.get("material_types", []):
            score += 10.0
        elif material_type == "unknown":
            score += 5.0
        
        # Domain match
        if domain in db_info.get("domains", []):
            score += 5.0
        
        # Capability match
        capabilities = db_info.get("capabilities", [])
        filter_keys = set(filters.keys()) if filters else set()
        
        # Check if database supports required filters
        if "formula" in filter_keys and "formula" in capabilities:
            score += 3.0
        if "elements" in filter_keys and "elements" in capabilities:
            score += 3.0
        if "space_group" in filter_keys and "space_group" in capabilities:
            score += 2.0
        if "band_gap" in filter_keys and "band_gap" in capabilities:
            score += 2.0
        if "sql_query" in filter_keys and "sql_query" in capabilities:
            score += 5.0  # SQL queries are special
        
        # Priority bonus (lower number = higher priority)
        priority = db_info.get("priority", 99)
        score += (10.0 - priority)
        
        if score > 0:
            db_scores[db_name] = score
    
    # Sort by score (descending) and return database names
    result = sorted(db_scores.items(), key=lambda x: x[1], reverse=True)
    result = [db_name for db_name, _ in result]
    
    # Fallback: if no databases selected, use default routes
    if not result:
        return plan_routes(material_type, domain)
    
    logging.info(f"Selected databases for {material_type}/{domain}: {result}")
    return result


def plan_routes(material_type: str, domain: str) -> List[str]:
    """
    Decide database route order based on material type (fallback method).
    """
    if material_type == "mof":
        if domain == "catalyst":
            return ["mofdbsql", "optimade"]
        return ["mofdbsql", "optimade"]
    
    if material_type == "crystal":
        if domain == "battery":
            return ["bohriumpublic", "openlam", "optimade"]
        if domain == "semiconductor":
            return ["bohriumpublic", "optimade", "openlam"]
        return ["bohriumpublic", "openlam", "optimade"]
    
    return ["bohriumpublic", "openlam", "optimade", "mofdbsql"]


def normalize_n_results(n_results: int, default: int = 5, max_results: int = 20) -> int:
    """
    Normalize n_results to valid range.
    
    Args:
        n_results: Requested number of results
        default: Default value if n_results is invalid
        max_results: Maximum allowed value
    
    Returns:
        Normalized n_results value
    """
    if not isinstance(n_results, int) or n_results < 1:
        return default
    return min(n_results, max_results)
