"""
MOFdb SQL Database Constants and Metadata

数据库分类、描述、规则和使用说明
"""
from typing import Dict, Any, List

# 数据库基本信息
DATABASE_NAME = "mofdbsql"
DATABASE_DISPLAY_NAME = "MOFdb SQL"
DATABASE_VERSION = "1.0"

# 数据库分类
MATERIAL_TYPES = ["mof"]  # 支持的材料类型
DOMAINS = ["catalyst", "gas_storage", "separation", "other"]  # 支持的领域

# 数据库描述
DESCRIPTION = (
    "MOF database with SQL query interface for complex searches. "
    "Supports advanced SQL queries with joins, window functions, CTEs, and statistical analysis. "
    "Provides direct access to SQLite database for sophisticated queries beyond traditional servers."
)

# 支持的搜索能力
CAPABILITIES = {
    "sql_query": {
        "description": "Direct SQL query support (SELECT and WITH statements only)",
        "example": "SELECT name, database, surface_area_m2g FROM mofs WHERE surface_area_m2g > 1000",
        "security": "Only SELECT and WITH queries allowed, no write operations",
    },
    "formula": {
        "description": "Chemical formula search via SQL",
        "example": "SELECT * FROM mofs WHERE formula LIKE '%Fe%'",
    },
    "elements": {
        "description": "Element-based search via SQL",
        "example": "SELECT * FROM mofs WHERE elements LIKE '%Fe%' AND elements LIKE '%O%'",
    },
    "surface_area": {
        "description": "Surface area filtering (m²/g or m²/cm³)",
        "example": "surface_area_m2g > 1000",
    },
    "pore_size": {
        "description": "Pore size distribution data",
        "example": "pore_size_distribution",
    },
    "void_fraction": {
        "description": "Void fraction filtering",
        "example": "void_fraction > 0.5",
    },
}

# 搜索规则
RULES = {
    "sql_query": {
        "allowed_statements": ["SELECT", "WITH"],
        "forbidden_keywords": [
            "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
            "TRUNCATE", "REPLACE", "MERGE", "EXEC", "EXECUTE", "CALL",
            "GRANT", "REVOKE", "COMMIT", "ROLLBACK", "SAVEPOINT"
        ],
        "security": "Read-only mode, URI mode connection",
        "limit": "Automatically adds LIMIT clause based on n_results",
    },
    "database_schema": {
        "main_tables": [
            "mofs: id, name, database, cif_path, n_atom, lcd, pld, url, hashkey, "
            "mofid, mofkey, pxrd, void_fraction, surface_area_m2g, surface_area_m2cm3, "
            "pore_size_distribution, batch_number"
        ],
        "related_tables": [
            "isotherms: adsorption data",
            "heats: heat of adsorption data",
        ],
    },
}

# 输出格式
SUPPORTED_OUTPUT_FORMATS = ["cif", "json"]

# 数据库优先级（用于智能选择）
PRIORITY = 2  # 2 = medium priority (use when SQL queries are needed)

# 数据库元数据
METADATA = {
    "source": "Local SQLite database",
    "database_type": "SQLite",
    "access": "Direct SQL queries",
    "data_quality": "High - curated MOF database",
    "update_frequency": "Static database",
}

# 使用示例
USAGE_EXAMPLES = [
    {
        "description": "Simple query by surface area",
        "query": "Find MOFs with surface area > 1000 m²/g",
        "sql": "SELECT name, database, surface_area_m2g FROM mofs WHERE surface_area_m2g > 1000 LIMIT 10",
    },
    {
        "description": "Complex query with aggregation",
        "query": "Count MOFs by database",
        "sql": "SELECT database, COUNT(*) as count FROM mofs GROUP BY database ORDER BY count DESC",
    },
    {
        "description": "Query with window functions",
        "query": "Top MOFs by surface area per database",
        "sql": """
            SELECT name, database, surface_area_m2g,
                   ROW_NUMBER() OVER (PARTITION BY database ORDER BY surface_area_m2g DESC) as rank
            FROM mofs
            WHERE rank <= 5
        """,
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

