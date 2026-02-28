"""
通过 MCP Streamable HTTP 调用远端 MrDice MCP Server。

用法：
  uv run python tests/test_mcp_remote.py --query "找一些 Fe2O3 材料" --n-results 3 --output-format cif

它会读取项目根目录 `.env` 的：
  - SERVER_URL                 (必需) 例如 http://host:50001/mcp；若服务端返回 404，可尝试根路径 http://host:port/
  - MR_DICE_MCP_TOKEN           (可选) 若服务端开启 token 校验，将通过 Authorization: Bearer 传递
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _load_env() -> None:
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        # fallback: allow running from other CWDs
        load_dotenv(override=True)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MrDice 远端 MCP 调用测试 (Streamable HTTP)")
    p.add_argument(
        "--query",
        type=str,
        default="",
        help="自然语言查询（若为空，则从 questions.json 批量读取并执行）",
    )
    p.add_argument("--n-results", type=int, default=6, help="返回结果数")
    p.add_argument(
        "--output-format",
        type=str,
        default="cif",
        choices=["cif", "json"],
        help="输出格式（服务端会将结构文件收集到 output_dir）",
    )
    p.add_argument(
        "--questions",
        type=str,
        default=str(Path(__file__).resolve().parent / "questions.json"),
        help="questions.json 路径（默认 tests/questions.json）",
    )
    p.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="最多执行多少条 query（0 表示不限制）",
    )
    p.add_argument("--list-tools", action="store_true", help="仅列出远端工具，不执行查询")
    return p.parse_args()


def _content_to_text(content: List[Any]) -> str:
    """
    将 CallToolResult.content 中的 TextContent 等尽量转成可读字符串（best-effort）。
    """
    parts: List[str] = []
    for c in content or []:
        t = getattr(c, "type", None)
        if t == "text":
            parts.append(getattr(c, "text", ""))
        else:
            # 其他类型（image/audio/resource_link/embedded_resource）直接 repr
            parts.append(repr(c))
    return "\n".join([p for p in parts if p])


def _load_questions(questions_path: Path) -> List[Dict[str, Any]]:
    """
    读取 questions.json，兼容两种格式：
    1) ["q1", ...]
    2) [{"id": 1, "enabled": true, "query": "..."}, ...]
    """
    if not questions_path.exists():
        raise FileNotFoundError(f"questions.json not found: {questions_path}")

    raw = json.loads(questions_path.read_text(encoding="utf-8"))
    items: List[Dict[str, Any]] = []
    if not raw:
        return items

    if isinstance(raw, list) and raw and isinstance(raw[0], str):
        for idx, q in enumerate(raw, 1):
            q = (q or "").strip()
            if not q:
                continue
            items.append({"id": idx, "enabled": True, "query": q})
        return items

    if isinstance(raw, list):
        for idx, item in enumerate(raw, 1):
            if not isinstance(item, dict):
                continue
            q = (item.get("query") or "").strip()
            if not q:
                continue
            qid = item.get("id") or idx
            enabled = item.get("enabled", True)
            items.append({"id": qid, "enabled": enabled, "query": q})
        return items

    raise ValueError("Unsupported questions.json format (expected list)")


async def _run() -> int:
    _load_env()

    server_url = (os.getenv("SERVER_URL") or "").strip()
    if not server_url:
        raise RuntimeError("SERVER_URL is not set (please configure it in project root .env)")

    token = (os.getenv("MR_DICE_MCP_TOKEN") or "").strip()
    headers: Dict[str, str] | None = None
    if token:
        headers = {"Authorization": f"Bearer {token}"}

    args = _parse_args()

    print("=" * 60)
    print("MrDice 远端 MCP 调用测试")
    print("=" * 60)
    print(f"SERVER_URL: {server_url}")
    print(f"MR_DICE_MCP_TOKEN: {'已设置 ✅' if token else '未设置'}")
    print("-" * 60)

    try:
        async with streamablehttp_client(server_url, headers=headers) as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                sid = None
                try:
                    sid = get_session_id()
                except Exception:
                    sid = None
                if sid:
                    print(f"session_id: {sid}")

                tools_res = await session.list_tools()
                tool_names = [t.name for t in (tools_res.tools or [])]
                print(f"远端 tools 数量: {len(tool_names)}")
                if args.list_tools:
                    for i, n in enumerate(tool_names, 1):
                        print(f"  [{i}] {n}")
                    return 0

                if "fetch_structures_from_db" not in tool_names:
                    print("❌ 远端未发现工具 fetch_structures_from_db")
                    for i, n in enumerate(tool_names, 1):
                        print(f"  [{i}] {n}")
                    return 2

                # --- build queries ---
                items: List[Dict[str, Any]] = []
                if (args.query or "").strip():
                    items = [{"id": 1, "enabled": True, "query": args.query.strip()}]
                else:
                    qpath = Path(args.questions).expanduser().resolve()
                    items = _load_questions(qpath)

                # filter enabled and apply max-items
                enabled_items = [x for x in items if x.get("enabled", True)]
                if args.max_items and args.max_items > 0:
                    enabled_items = enabled_items[: args.max_items]

                if not enabled_items:
                    print("⚠️  没有可执行的 queries（请检查 --query 或 questions.json）")
                    return 0

                total_t0 = time.perf_counter()
                summary: List[Dict[str, Any]] = []

                for item in enabled_items:
                    qid = item.get("id", "-")
                    q = (item.get("query") or "").strip()
                    if not q:
                        continue

                    print(f"\n[{qid}] 查询: {q}")
                    print(f"n_results: {args.n_results} | output_format: {args.output_format}")
                    print("-" * 60)

                    t0 = time.perf_counter()
                    try:
                        call_res = await session.call_tool(
                            "fetch_structures_from_db",
                            arguments={
                                "query": q,
                                "n_results": int(args.n_results),
                                "output_format": args.output_format,
                            },
                        )
                        elapsed_s = time.perf_counter() - t0
                        print(f"远端调用耗时: {elapsed_s:.3f}s ({elapsed_s * 1000:.1f}ms)")

                        if getattr(call_res, "isError", False):
                            print("❌ 远端工具调用失败 (isError=true)")
                            txt = _content_to_text(getattr(call_res, "content", []) or [])
                            if txt:
                                print(txt)
                            if getattr(call_res, "structuredContent", None):
                                print(json.dumps(call_res.structuredContent, ensure_ascii=False, indent=2))
                            summary.append(
                                {"id": qid, "query": q, "ok": False, "seconds": elapsed_s, "error": "isError=true"}
                            )
                            continue

                        data = getattr(call_res, "structuredContent", None)
                        if isinstance(data, dict):
                            # --- strict success criteria ---
                            # Success only if:
                            # - code == 0
                            # - errors is empty (or all values empty)
                            # - found structures AND returned > 0 AND produced files
                            try:
                                code = int(data.get("code")) if data.get("code") is not None else 0
                            except Exception:
                                code = 0

                            n_found = int(data.get("n_found") or 0)
                            returned = int(data.get("returned") or 0)
                            files = data.get("files") or []
                            files_count = len(files) if isinstance(files, list) else 0

                            errors_obj = data.get("errors")
                            has_errors = False
                            if isinstance(errors_obj, dict):
                                for _k, _v in errors_obj.items():
                                    if _v is None:
                                        continue
                                    if str(_v).strip():
                                        has_errors = True
                                        break
                            elif errors_obj:
                                has_errors = True

                            ok = (
                                (code == 0)
                                and (not has_errors)
                                and (n_found > 0)
                                and (returned > 0)
                                and (files_count > 0)
                            )

                            if ok:
                                print("✅ Success（无报错且找到结构）")
                            else:
                                print("⚠️  Not success（有报错或未找到结构/文件）")
                            print(f"n_found: {n_found} | returned: {returned} | files: {files_count}")
                            print(f"code: {code} | errors: {'有' if has_errors else '无'}")
                            if data.get("output_dir"):
                                print(f"output_dir: {data.get('output_dir')}")
                            if files_count:
                                for i, fp in enumerate(files[:5], 1):
                                    print(f"  file[{i}]: {fp}")
                                if files_count > 5:
                                    print(f"  ... 还有 {files_count - 5} 个文件未展示")
                            if has_errors and isinstance(errors_obj, dict):
                                # 只展示非空 errors
                                non_empty = {
                                    k: v for k, v in errors_obj.items() if v is not None and str(v).strip()
                                }
                                if non_empty:
                                    print("errors 明细：")
                                    print(json.dumps(non_empty, ensure_ascii=False, indent=2))
                            summary.append(
                                {
                                    "id": qid,
                                    "query": q,
                                    "ok": ok,
                                    "seconds": elapsed_s,
                                    "n_found": n_found,
                                    "code": code,
                                    "has_errors": has_errors,
                                    "returned": returned,
                                    "files_count": files_count,
                                }
                            )
                        else:
                            # fallback: print text content
                            txt = _content_to_text(getattr(call_res, "content", []) or [])
                            print("✅ 远端返回 content：")
                            print(txt or "(empty)")
                            summary.append({"id": qid, "query": q, "ok": True, "seconds": elapsed_s})

                    except Exception as e:
                        elapsed_s = time.perf_counter() - t0
                        print(f"❌ 调用异常: {e}")
                        summary.append({"id": qid, "query": q, "ok": False, "seconds": elapsed_s, "error": str(e)})

                total_elapsed = time.perf_counter() - total_t0
                ok_n = sum(1 for x in summary if x.get("ok"))
                fail_n = len(summary) - ok_n
                print("\n" + "=" * 60)
                print("测试汇总")
                print("=" * 60)
                print(f"总 queries: {len(summary)} | 成功: {ok_n} | 失败: {fail_n} | 总耗时: {total_elapsed:.3f}s")
                for i, x in enumerate(summary, 1):
                    status = "OK" if x.get("ok") else "FAIL"
                    msg = f"{i}. [ID={x.get('id')}] [{status}] {x.get('seconds', 0):.3f}s - {x.get('query')}"
                    if x.get("ok") and "n_found" in x:
                        msg += f" | n_found: {int(x.get('n_found') or 0)}"
                    if not x.get("ok"):
                        msg += f" | error: {x.get('error', '')}"
                    print(msg)

                return 0 if fail_n == 0 else 1
    except Exception as e:
        print("❌ MCP 连接/请求失败")
        print(f"SERVER_URL: {server_url}")

        err_text = str(e).lower()
        if "404" in err_text or "not found" in err_text:
            print("  提示: 若服务端日志显示 POST /mcp 404，说明路径不匹配。")
            print("  - 可尝试 SERVER_URL 改为根路径，例如: http://host:port/")
            print("  - 或确认远端服务用同一代码、且未在反向代理中改写路径。")

        def _print_exceptions(exc: BaseException, prefix: str = "  ") -> None:
            if hasattr(exc, "exceptions") and getattr(exc, "exceptions"):
                subs = getattr(exc, "exceptions")
                for i, sub in enumerate(subs, 1):
                    print(f"{prefix}[{i}] {type(sub).__name__}: {sub}")
                    _print_exceptions(sub, prefix=prefix + "    ")
            else:
                # 叶子异常：可打印简短 traceback 便于排查
                pass

        if hasattr(e, "exceptions") and getattr(e, "exceptions"):
            for i, sub in enumerate(getattr(e, "exceptions"), 1):
                print(f"  [{i}] {type(sub).__name__}: {sub}")
                _print_exceptions(sub, prefix="      ")
        else:
            print(f"  {type(e).__name__}: {e}")

        if os.getenv("MR_DICE_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()

