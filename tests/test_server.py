"""
快速测试服务器功能的脚本
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mrdice_server.core.server import mrdice_search


def _format_duration(seconds: float) -> str:
    total_seconds = int(round(seconds))
    minutes = total_seconds // 60
    remaining_seconds = total_seconds % 60
    return f"{minutes}min{remaining_seconds}s"


async def test_search():
    """测试搜索功能"""
    print("=" * 60)
    print("测试 MrDice 搜索功能")
    print("=" * 60)

    questions_path = project_root / "questions.json"
    with questions_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    # 兼容两种格式：
    # 1) ["q1", ...]
    # 2) [{"id": 1, "enabled": true, "query": "..."}, ...]
    items = []
    if raw:
        if isinstance(raw[0], str):
            for idx, q in enumerate(raw, 1):
                if not (q or "").strip():
                    continue
                items.append({"id": idx, "enabled": True, "query": q})
        else:
            for idx, item in enumerate(raw, 1):
                if not isinstance(item, dict):
                    continue
                q = (item.get("query") or "").strip()
                if not q:
                    continue
                qid = item.get("id") or idx
                enabled = item.get("enabled", True)
                items.append({"id": qid, "enabled": enabled, "query": q})


    total_t0 = time.perf_counter()
    summary = []
    
    for item in items:
        if not item.get("enabled", True):
            continue
        qid = item["id"]
        query = item["query"]
        print(f"\n[{qid}] 查询: {query}")
        print("-" * 60)
        t0 = time.perf_counter()
        
        try:
            result = await mrdice_search(
                query=query,
                n_results=6,
                output_format="cif"
            )
            n_found = int(result.get("n_found") or 0)

            print(f"✅ 搜索成功")
            print(f"找到结果数: {n_found}")
            print(f"返回结果数: {result['returned']}")
            print(f"输出目录: {result.get('output_dir')}")
            files = result.get("files") or []
            files_count = len(files)
            ok = n_found > 0 and files_count > 0
            print(f"文件数量: {files_count}")
            for i, file_path in enumerate(files, 1):
                print(f"  [{i}] {file_path}")

            if result['results']:
                print(f"\n前 {min(3, len(result['results']))} 个结果:")
                for i, r in enumerate(result['results'][:3], 1):
                    print(f"  {i}. {r.get('formula', 'N/A')} - {r.get('name', 'N/A')}")
            else:
                print("⚠️  未找到结果")

            elapsed = time.perf_counter() - t0
            summary.append(
                {
                    "id": qid,
                    "query": query,
                    "ok": ok,
                    "seconds": elapsed,
                    "n_found": n_found,
                    "files_count": files_count,
                }
            )
            print(f"\n耗时: {elapsed:.3f}s")
                
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"❌ 搜索失败: {e}")
            import traceback
            traceback.print_exc()
            summary.append(
                {
                    "id": qid,
                    "query": query,
                    "ok": False,
                    "seconds": elapsed,
                    "error": str(e),
                }
            )
            print(f"\n耗时: {elapsed:.3f}s")

    total_elapsed = time.perf_counter() - total_t0
    ok_n = sum(1 for x in summary if x["ok"])
    fail_n = len(summary) - ok_n
    total_found = sum(int(x.get("n_found") or 0) for x in summary if x["ok"])

    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    print(
        f"总 queries: {len(summary)} | 成功: {ok_n} | 失败: {fail_n} | "
        f"总耗时: {total_elapsed:.3f}s | 总找到结构数: {total_found}"
    )
    for i, x in enumerate(summary, 1):
        status = "OK" if x["ok"] else "FAIL"
        msg = f"{i}. [ID={x.get('id')}] [{status}] {x['seconds']:.3f}s - {x['query']}"
        if x["ok"]:
            msg += f" | 找到结构数: {int(x.get('n_found') or 0)}"
        if not x["ok"]:
            msg += f" | error: {x.get('error', '')}"
        print(msg)

    # 写入 summary_$timestamp.md
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = project_root / f"summary_{ts}.md"
    lines = []
    lines.append("# MrDice 搜索测试汇总\n")
    lines.append(f"- 总 queries: {len(summary)}\n")
    lines.append(f"- 成功: {ok_n}\n")
    lines.append(f"- 失败: {fail_n}\n")
    lines.append(f"- 总耗时: {_format_duration(total_elapsed)}\n")
    lines.append(f"- 总找到结构数: {total_found}\n")
    lines.append("\n")
    lines.append("## 明细\n\n")
    lines.append("| # | ID | 状态 | 用时 | 找到结构数 | 文件数 | Query |\n")
    lines.append("|---|----|------|------|------------|--------|-------|\n")
    for i, x in enumerate(summary, 1):
        status = "OK" if x["ok"] else "FAIL"
        qid = x.get("id", "-")
        n_found = int(x.get("n_found") or 0) if x["ok"] else 0
        files_count = int(x.get("files_count") or 0) if x["ok"] else 0
        dur_str = _format_duration(x["seconds"])
        query = x["query"].replace("|", "\\|")
        lines.append(
            f"| {i} | {qid} | {status} | {dur_str} | {n_found} | {files_count} | {query} |\n"
        )
    summary_path.write_text("".join(lines), encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(test_search())
