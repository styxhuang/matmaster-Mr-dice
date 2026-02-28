#!/usr/bin/env python3
"""
OpenLAM 独立调用脚本：通过 Python 或命令行查询 OpenLAM 晶体结构，支持传入 Bohrium 凭证。

为何使用 BOHRIUM_ACCESS_KEY？
  OpenLAM Database 托管在 Bohrium（dp.tech）平台上，查询接口为 openapi.dp.tech。
  访问该 API 需要用户维度的访问密钥，用于鉴权。密钥在以下地址获取：
  https://bohrium.dp.tech/settings/user

  BOHRIUM_PROJECT_ID / BOHRIUM_USER_ID 为可选，当前 OpenLAM 查询 API 仅使用 access_key；
  保留参数便于与现有环境变量一致，或后续扩展（如计费、配额等）。

参考：https://github.com/deepmodeling/openlam?tab=readme-ov-file

命令行示例：
  uv run python scripts/openlam_cli.py --access-key YOUR_KEY --formula Fe2O3 --limit 5
  uv run python scripts/openlam_cli.py --formula Fe2O3 --output-dir ./out   # 使用环境变量中的 BOHRIUM_ACCESS_KEY

Python 调用示例：
  from scripts.openlam_cli import query_structures, set_bohrium_env
  data = query_structures(formula="Fe2O3", limit=5, access_key="YOUR_KEY")
  for cs in data["items"]:
      print(cs.formula, cs.energy)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 保证从项目根可导入 mrdice_server 及 openlam 子模块
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_openlam_root = _project_root / "mrdice_server" / "database" / "openlam_database" / "openlam"
if _openlam_root.exists() and str(_openlam_root) not in sys.path:
    sys.path.insert(0, str(_openlam_root))

from mrdice_server.database.openlam_database.utils import set_bohrium_env


def query_structures(
    formula: Optional[str] = None,
    min_energy: Optional[float] = None,
    max_energy: Optional[float] = None,
    min_submission_time: Optional[datetime] = None,
    max_submission_time: Optional[datetime] = None,
    offset: int = 0,
    limit: int = 10,
    *,
    access_key: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    查询 OpenLAM 晶体结构（可通过 Python 直接调用）。

    参数
    -----
    formula, min_energy, max_energy, min_submission_time, max_submission_time, offset, limit
        与 OpenLAM query_by_offset 一致。
    access_key : str, optional
        Bohrium 访问密钥；不传则使用环境变量 BOHRIUM_ACCESS_KEY。
    project_id : str or int, optional
        可选，会写入 BOHRIUM_PROJECT_ID。
    user_id : str or int, optional
        可选，会写入 BOHRIUM_USER_ID。

    返回
    -----
    dict
        {"items": [CrystalStructure, ...], "nextStartId": int}
    """
    set_bohrium_env(access_key=access_key, project_id=project_id, user_id=user_id)
    from lam_optimize.db import CrystalStructure

    return CrystalStructure.query_by_offset(
        formula=formula,
        min_energy=min_energy,
        max_energy=max_energy,
        min_submission_time=min_submission_time,
        max_submission_time=max_submission_time,
        offset=offset,
        limit=limit,
    )


def run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="OpenLAM 查询：可从命令行或 Python 传入 BOHRIUM_ACCESS_KEY 等凭证。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--access-key",
        type=str,
        default=os.environ.get("BOHRIUM_ACCESS_KEY", ""),
        help="Bohrium 访问密钥（也可用环境变量 BOHRIUM_ACCESS_KEY）",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=os.environ.get("BOHRIUM_PROJECT_ID", ""),
        help="Bohrium 项目 ID（可选，环境变量 BOHRIUM_PROJECT_ID）",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=os.environ.get("BOHRIUM_USER_ID", ""),
        help="Bohrium 用户 ID（可选，环境变量 BOHRIUM_USER_ID）",
    )
    parser.add_argument("--formula", type=str, default="", help="化学式筛选，如 Fe2O3")
    parser.add_argument("--limit", type=int, default=10, help="返回条数")
    parser.add_argument("--offset", type=int, default=0, help="分页偏移")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="若指定，将结果保存为 CIF/JSON 到该目录",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["cif", "json", "both"],
        default="cif",
        help="保存格式",
    )
    args = parser.parse_args()

    if not args.access_key:
        print("错误: 未提供 BOHRIUM_ACCESS_KEY（--access-key 或环境变量）", file=sys.stderr)
        print("获取密钥: https://bohrium.dp.tech/settings/user", file=sys.stderr)
        sys.exit(1)

    set_bohrium_env(
        access_key=args.access_key or None,
        project_id=args.project_id or None,
        user_id=args.user_id or None,
    )

    data = query_structures(
        formula=args.formula.strip() or None,
        limit=args.limit,
        offset=args.offset,
        access_key=args.access_key,
        project_id=args.project_id or None,
        user_id=args.user_id or None,
    )
    items: List[Any] = data.get("items") or []
    next_id = data.get("nextStartId", 0)

    print(f"查询到 {len(items)} 条，nextStartId={next_id}")
    for i, cs in enumerate(items):
        print(f"  [{i+1}] id={getattr(cs, 'id', '?')} formula={getattr(cs, 'formula', '?')} energy={getattr(cs, 'energy', '?')}")

    if args.output_dir and items:
        args.output_dir = Path(args.output_dir).resolve()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        from mrdice_server.database.openlam_database.utils import save_structures_openlam

        formats: List[str] = ["cif", "json"] if args.output_format == "both" else [args.output_format]
        save_structures_openlam(items=items, output_dir=args.output_dir, output_formats=formats)
        print(f"已保存到: {args.output_dir}")


if __name__ == "__main__":
    run_cli()
