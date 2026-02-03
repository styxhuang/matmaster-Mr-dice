import argparse
import logging
import json
import hashlib
import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Literal, TypedDict
from anyio import to_thread

from dp.agent.server import CalculationMCPServer
from utils import *

# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="MOFdb SQL MCP Server")
    parser.add_argument('--port', type=int, default=50006, help='Server port (default: 50006)')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    try:
        return parser.parse_args()
    except SystemExit:
        class Args:
            port = 50006
            host = '0.0.0.0'
            log_level = 'INFO'
        return Args()

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

# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("MOFDBSQLServer", port=args.port, host=args.host)

# 数据库路径
DB_PATH = '/home/MOF_SQL_test/mof_data/mof_database.db'

# === MCP TOOL ===
@mcp.tool()
async def fetch_mofs_sql(
    sql: str,
    n_results: int = 10,
    output_formats: List[Format] = ["cif", "json"]
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
        - cleaned_structures: List of results dicts.
        - n_found: Number of results returned.
    """

    # === Step 1: SQL Security Check ===
    if not os.path.exists(DB_PATH):
        return {
            "output_dir": Path(),
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"数据库不存在: {DB_PATH}",
        }
    
    # 使用utils中的安全检查函数
    try:
        validate_sql_security(sql)
    except Exception as e:
        return {
            "output_dir": Path(),
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"SQL安全检查失败: {str(e)}",
        }
    
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
        logging.error(f"数据库查询错误: {e}")
        return {
            "output_dir": Path(),
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"数据库查询错误: {str(e)}",
        }
    except Exception as e:
        logging.error(f"查询执行错误: {e}")
        return {
            "output_dir": Path(),
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"查询执行错误: {str(e)}",
        }

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
    try:
        cleaned, warnings = await to_thread.run_sync(lambda: save_mofs(
            results,
            output_dir,
            output_formats
        ))
    except Exception as e:
        logging.error(f"保存结构时出错: {e}")
        return {
            "output_dir": output_dir,
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"保存结构时出错: {str(e)}",
        }

    cleaned = cleaned[:MAX_RETURNED_STRUCTS]
    n_found = len(cleaned)

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
        "n_found": n_found,
        "cleaned_structures": cleaned,
        "code": -9999 if n_found == 0 else 0,
        "message": "Success",
    }

# === START SERVER ===
if __name__ == "__main__":
    logging.info(f"Starting MOFdb SQL MCP Server on {args.host}:{args.port}")
    logging.info(f"Database path: {DB_PATH}")
    mcp.run(transport="sse")