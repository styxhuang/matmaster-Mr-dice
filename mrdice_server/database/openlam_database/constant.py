"""
OpenLAM Database Constants and Metadata

数据库分类、描述、规则和使用说明
"""
from typing import Dict, Any, List

# 数据库基本信息
DATABASE_NAME = "openlam"
DATABASE_DISPLAY_NAME = "OpenLAM"
DATABASE_VERSION = "1.0"

# 数据库分类
MATERIAL_TYPES = ["crystal"]  # 支持的材料类型
DOMAINS = ["semiconductor", "battery", "perovskite", "other"]  # 支持的领域

# 数据库描述
DESCRIPTION = (
    "Open-source lattice matching database for crystal structures. "
    "Provides crystal structures with energy data and submission time information. "
    "Optimized for lattice matching and crystal structure search."
)

# 支持的搜索能力
CAPABILITIES = {
    "formula": {
        "description": "Chemical formula search",
        "example": "Fe2O3",
    },
    "elements": {
        "description": "Element-based search",
        "example": ["Fe", "O"],
    },
    "energy": {
        "description": "Energy range filtering in eV",
        "example": {"min": -5.0, "max": 0.0},
        "unit": "eV",
        "aliases": ["min_energy", "max_energy"],
    },
    "submission_time": {
        "description": "Submission time range filtering",
        "example": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
        "format": "ISO 8601 UTC format",
        "aliases": ["min_submission_time", "max_submission_time"],
    },
    "lattice_parameters": {
        "description": "Lattice parameter matching",
        "note": "Used for lattice matching optimization",
    },
}

# 搜索规则
RULES = {
    "formula": {
        "normalization": "Subscript/superscript numbers are automatically normalized",
        "case_sensitive": False,
    },
    "elements": {
        "logic": "AND logic (all elements must be present)",
        "case_sensitive": False,
    },
    "energy": {
        "format": "Range: {min: float, max: float} in eV",
        "validation": "min <= max",
    },
    "submission_time": {
        "format": "ISO 8601 UTC format: YYYY-MM-DDTHH:MM:SSZ",
        "validation": "Valid ISO 8601 datetime string",
    },
}

# 输出格式
SUPPORTED_OUTPUT_FORMATS = ["cif", "json"]

# 数据库优先级（用于智能选择）
PRIORITY = 2  # 2 = medium priority

# 数据库元数据
METADATA = {
    "source": "OpenLAM API",
    "api_type": "REST API",
    "data_quality": "High - optimized structures",
    "update_frequency": "Regular updates",
    "specialization": "Lattice matching and crystal optimization",
}

# 使用示例
USAGE_EXAMPLES = [
    {
        "description": "Search by formula and energy",
        "query": "Find Fe2O3 structures with energy < -5.0 eV",
        "filters": {
            "formula": "Fe2O3",
            "energy": {"min": None, "max": -5.0},
        },
    },
    {
        "description": "Search by submission time",
        "query": "Structures submitted in 2024",
        "filters": {
            "submission_time": {
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-12-31T23:59:59Z",
            },
        },
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

