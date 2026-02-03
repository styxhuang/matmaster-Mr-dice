import json
import hashlib
import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Literal, TypedDict
import re

from utils import *

# === OUTPUT TYPE ===
Format = Literal["cif", "json"]

class FetchResult(TypedDict):
    output_dir: Path
    cleaned_structures: List[dict]
    n_found: int
    code: int
    message: str

BASE_OUTPUT_DIR = Path("materials_data_mofdb")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETURNED_STRUCTS = 30

# 数据库路径
DB_PATH = '/bohr/MOF-SQL-nj9w/v1/mof_database.db'

def fetch_mofs(
    sql: str,
    n_results: int = 10,
    output_formats: List[Format] = ["cif"]
) -> FetchResult:
    """
    🧱 Fetch MOFs from local SQLite database using SQL queries and save them to disk.

    🔍 What this tool does:
    -----------------------------------
    - Executes SQL queries against the local MOF SQLite database.
    - Supports complex filtering, joins, and aggregations through SQL.
    - Saves results in `.cif` and/or `.json` formats.
    - Automatically creates a tagged output folder and writes a manifest.

    📤 Returns:
    -----------------------------------
    FetchResult (dict) with:
        - output_dir: Path to the output folder.
        - cleaned_structures: List of cleaned MOF dicts.
        - n_found: Number of MOFs returned.
    """

    # === Step 1: SQL Security Check ===
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"数据库不存在: {DB_PATH}")
    
    # 使用utils中的安全检查函数
    validate_sql_security(sql)

    # === Step 2: Process SQL Query ===
    # 自动添加 LIMIT 子句，确保与 n_results 保持一致
    processed_sql = sql.strip()
    
    # 移除末尾的分号，避免多语句问题
    if processed_sql.endswith(';'):
        processed_sql = processed_sql[:-1]
    
    if not processed_sql.upper().endswith('LIMIT'):
        # 检查是否已经有 LIMIT 子句
        if 'LIMIT' not in processed_sql.upper():
            processed_sql += f" LIMIT {n_results}"
        else:
            # 如果已有 LIMIT，替换为 n_results
            import re
            processed_sql = re.sub(r'\s+LIMIT\s+\d+', f' LIMIT {n_results}', processed_sql, flags=re.IGNORECASE)
    
    try:
        # 使用只读模式连接数据库，防止任何修改操作
        with sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row  # 让结果可以按列名访问
            cursor = conn.cursor()
            cursor.execute(processed_sql)
            
            # 获取结果并以字典形式返回
            results = []
            for row in cursor.fetchall():
                results.append(dict(row))
                
    except sqlite3.Error as e:
        print(f"数据库查询错误: {e}")
        results = []
    except Exception as e:
        print(f"查询执行错误: {e}")
        results = []

    n_found = len(results)

    # === Step 2: Build output folder ===
    filter_str = json.dumps({
        "sql": processed_sql,
        "n_results": n_results
    }, sort_keys=True, default=str)
    tag = "sql_query"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha1(filter_str.encode("utf-8")).hexdigest()[:8]
    output_dir = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short_hash}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # === Step 3: Save ===
    cleaned, warnings = save_mofs(
        results,
        output_dir,
        output_formats
    )

    cleaned = cleaned[:MAX_RETURNED_STRUCTS]

    # === Step 4: Manifest ===
    manifest = {
        "filters": {
            "sql": processed_sql,
            "n_results": n_results,
        },
        "n_found": n_found,
        "formats": output_formats,
        "output_dir": str(output_dir),
        "warnings": warnings,
    }
    (output_dir / "summary.json").write_text(json.dumps(manifest, indent=2))

    return {
        "output_dir": output_dir,
        "n_found": len(cleaned),  # Calculate from cleaned_structures
        "cleaned_structures": cleaned,  # Return query results directly
        "code": 0,
        "message": "Success",
    }

if __name__ == "__main__":
    # 示例用法
    print("MOF SQL Server 示例")
    print("使用 fetch_mofs() 函数执行SQL查询")
    print("示例: fetch_mofs('SELECT * FROM mofs LIMIT 5', n_results=5, output_formats=['json'])")
    print("运行 python test.py 查看完整测试")