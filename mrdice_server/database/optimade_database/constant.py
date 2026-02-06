"""
OPTIMADE Database Constants and Metadata

数据库分类、描述、规则和使用说明
"""
from typing import Dict, Any, List

# 数据库基本信息
DATABASE_NAME = "optimade"
DATABASE_DISPLAY_NAME = "OPTIMADE"
DATABASE_VERSION = "1.0"

# 数据库分类
MATERIAL_TYPES = ["crystal", "mof"]  # 支持的材料类型
DOMAINS = ["semiconductor", "catalyst", "battery", "perovskite", "other"]  # 支持的领域

# 数据库描述
DESCRIPTION = (
    "Multi-provider materials database with standardized OPTIMADE API. "
    "Aggregates data from multiple providers (MP, OQMD, COD, etc.) with unified query interface. "
    "Supports complex filtering and parallel queries across providers."
)

# 支持的搜索能力
CAPABILITIES = {
    "formula": {
        "description": "Chemical formula search (reduced or full formula)",
        "example": "Fe2O3",
        "variants": ["chemical_formula_reduced", "chemical_formula"],
    },
    "elements": {
        "description": "Element-based search with HAS ALL, HAS ANY, HAS ONLY operators",
        "example": 'elements HAS ALL "Fe", "O"',
        "operators": ["HAS ALL", "HAS ANY", "HAS ONLY"],
    },
    "space_group": {
        "description": "Space group filtering",
        "example": "space_group = 225",
        "format": "Integer space group number",
    },
    "band_gap": {
        "description": "Band gap range filtering (provider-specific property names)",
        "example": {"min": 0.5, "max": 3.0},
        "unit": "eV",
        "note": "Property names vary by provider (e.g., _oqmd_band_gap, _gnome_bandgap)",
    },
    "filter_string": {
        "description": "OPTIMADE filter string (supports complex queries)",
        "example": 'elements HAS ALL "Al" AND nelements = 2',
        "format": "OPTIMADE filter syntax",
    },
}

# 支持的提供商
PROVIDERS = [
    "alexandria",
    "cmr",
    "cod",
    "mp",
    "mpdd",
    "mpds",
    "nmd",
    "odbx",
    "omdb",
    "oqmd",
    "tcod",
    "twodmatpedia",
]

# 搜索规则
RULES = {
    "filter_string": {
        "syntax": "OPTIMADE filter syntax",
        "operators": [
            "=", "!=", "<", "<=", ">", ">=",
            "HAS ALL", "HAS ANY", "HAS ONLY",
            "AND", "OR", "NOT",
        ],
        "examples": [
            'elements HAS ALL "Fe", "O"',
            'nelements = 2',
            'space_group = 225',
            'chemical_formula_reduced = "Fe2O3"',
        ],
    },
    "band_gap": {
        "format": "Range: {min: float, max: float} in eV",
        "validation": "min <= max, both >= 0",
        "note": "Automatically maps to provider-specific property names",
    },
    "providers": {
        "selection": "Can specify specific providers or use all default providers",
        "parallel": "Queries run in parallel across selected providers",
    },
}

# 输出格式
SUPPORTED_OUTPUT_FORMATS = ["cif", "json"]

# 数据库优先级（用于智能选择）
PRIORITY = 3  # 3 = lower priority (use as fallback or for multi-provider queries)

# 数据库元数据
METADATA = {
    "source": "OPTIMADE API (multiple providers)",
    "api_standard": "OPTIMADE v1.0",
    "providers": PROVIDERS,
    "data_quality": "Varies by provider",
    "update_frequency": "Varies by provider",
    "specialization": "Multi-provider aggregation",
}

# 使用示例
USAGE_EXAMPLES = [
    {
        "description": "Search by elements",
        "query": "Find structures with Fe and O",
        "filter": 'elements HAS ALL "Fe", "O"',
    },
    {
        "description": "Search by space group and band gap",
        "query": "Cubic structures with band gap > 2.0 eV",
        "base_filter": 'space_group = 225',
        "band_gap": {"min": 2.0, "max": None},
    },
    {
        "description": "Complex filter",
        "query": "Binary compounds with specific elements",
        "filter": 'elements HAS ALL "Al", "O" AND nelements = 2',
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
    "providers": PROVIDERS,
}

