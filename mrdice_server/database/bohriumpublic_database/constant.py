"""
Bohrium Public Database Constants and Metadata

数据库分类、描述、规则和使用说明
"""
from typing import Dict, Any, List

# 数据库基本信息
DATABASE_NAME = "bohriumpublic"
DATABASE_DISPLAY_NAME = "Bohrium Public"
DATABASE_VERSION = "1.0"

# 数据库分类
MATERIAL_TYPES = ["crystal"]  # 支持的材料类型
DOMAINS = ["semiconductor", "catalyst", "battery", "perovskite", "other"]  # 支持的领域

# 数据库描述
DESCRIPTION = (
    "Large-scale crystal structure database with formation energy and band gap data. "
    "Provides access to millions of crystal structures with comprehensive property data."
)

# 支持的搜索能力
CAPABILITIES = {
    "formula": {
        "description": "Chemical formula search (supports fuzzy and exact match)",
        "example": "Fe2O3",
        "match_modes": [0, 1],  # 0=fuzzy, 1=exact
    },
    "elements": {
        "description": "Element-based search (requires all specified elements)",
        "example": ["Fe", "O"],
    },
    "space_group": {
        "description": "Space group number search",
        "example": 225,
        "range": [1, 230],
    },
    "band_gap": {
        "description": "Band gap range in eV",
        "example": {"min": 0.5, "max": 3.0},
        "unit": "eV",
    },
    "formation_energy": {
        "description": "Predicted formation energy range in eV",
        "example": {"min": -5.0, "max": 0.0},
        "unit": "eV",
        "alias": "predicted_formation_energy",
    },
    "atom_count": {
        "description": "Number of atoms range",
        "example": [10, 100],
        "alias": "atom_count_range",
    },
}

# 搜索规则
RULES = {
    "formula": {
        "normalization": "Subscript/superscript numbers are automatically normalized",
        "match_mode": "0 = fuzzy match, 1 = exact match (default: 1)",
        "case_sensitive": False,
    },
    "elements": {
        "logic": "AND logic (all elements must be present)",
        "case_sensitive": False,
    },
    "space_group": {
        "format": "Integer space group number (1-230)",
        "validation": "Must be valid space group number",
    },
    "band_gap": {
        "format": "Range: [min, max] in eV",
        "validation": "min <= max, both >= 0",
    },
    "formation_energy": {
        "format": "Range: [min, max] in eV",
        "validation": "min <= max",
    },
}

# 输出格式
SUPPORTED_OUTPUT_FORMATS = ["cif", "json"]

# 数据库优先级（用于智能选择）
PRIORITY = 1  # 1 = highest priority

# 数据库元数据
METADATA = {
    "source": "Bohrium Core API",
    "api_endpoint": "/api/v1/crystal/list",
    "authentication": "X-User-Id header required",
    "rate_limit": "Not specified",
    "data_quality": "High - validated structures with DFT calculations",
    "update_frequency": "Regular updates",
}

# 使用示例
USAGE_EXAMPLES = [
    {
        "description": "Search by formula",
        "query": "Fe2O3",
        "filters": {"formula": "Fe2O3"},
    },
    {
        "description": "Search by elements and band gap",
        "query": "Find semiconductors with Fe and O, band gap > 2.0 eV",
        "filters": {
            "elements": ["Fe", "O"],
            "band_gap": {"min": 2.0, "max": None},
        },
    },
    {
        "description": "Search by space group",
        "query": "Cubic structures (space group 225)",
        "filters": {"space_group": 225},
    },
]

# 完整的数据库描述字典（用于路由选择）
DATABASE_INFO: Dict[str, Any] = {
    "name": DATABASE_DISPLAY_NAME,
    "database_id": DATABASE_NAME,
    "description": DESCRIPTION,
    "material_types": MATERIAL_TYPES,
    "domains": DOMAINS,
    "capabilities": list(CAPABILITIES.keys()),
    "priority": PRIORITY,
    "metadata": METADATA,
    "rules": RULES,
    "usage_examples": USAGE_EXAMPLES,
    "supported_formats": SUPPORTED_OUTPUT_FORMATS,
}

