import argparse
import asyncio
import hashlib
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from dotenv import load_dotenv
from dp.agent.server import CalculationMCPServer
from urllib.parse import parse_qs

from starlette.routing import Route
from starlette.types import Receive, Scope, Send

def _load_env() -> None:
    """
    Load environment variables from the project root `.env`.

    Do not rely on current working directory (tools / ADK web may import this module).
    """
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        return

    # Fallback to CWD for compatibility
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=True)


_load_env()

from .config import DEFAULT_N_RESULTS, DEFAULT_OUTPUT_FORMAT, MAX_N_RESULTS, get_bohrium_output_dir, get_data_dir
from .preprocessor import preprocess_query, relax_to_element_only_filter
from ..search.ranker import rank_results
from ..search.router import normalize_n_results
from ..models.schema import build_response, SearchResult
from ..search.searcher import ALL_DATABASE_NAMES, search_databases_parallel_with_errors


def _merge_results_multi_db(
    db_results: Dict[str, List[SearchResult]],
    db_names: List[str],
) -> List[SearchResult]:
    """
    Merge results from multiple DBs in round-robin order so each source appears
    interleaved; avoids returning one DB's results in a single block.
    """
    lists = [db_results.get(db, []) for db in db_names]
    out: List[SearchResult] = []
    idx = 0
    while True:
        added = 0
        for L in lists:
            if idx < len(L):
                out.append(L[idx])
                added += 1
        if added == 0:
            break
        idx += 1
    return out


def _take_n_results_with_sources(
    ranked: List[SearchResult],
    n_results: int,
    db_names: List[str],
) -> List[SearchResult]:
    """
    Take up to n_results from ranked, ensuring at least one result from each
    requested DB that appears in ranked (so returned list includes all DBs).
    """
    if not ranked or n_results <= 0:
        return []
    if len(db_names) <= 1:
        return ranked[:n_results]
    # Ensure one from each source first, then fill by rank
    by_source: Dict[str, List[SearchResult]] = {}
    for r in ranked:
        src = (r.get("source") or "").strip() or "unknown"
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(r)
    chosen_ids: set = set()
    out: List[SearchResult] = []

    def add_one(r: SearchResult) -> bool:
        key = (r.get("source"), r.get("id"), r.get("name"))
        if key in chosen_ids:
            return False
        chosen_ids.add(key)
        out.append(r)
        return True

    for db in db_names:
        if db in by_source and by_source[db]:
            add_one(by_source[db][0])
    for r in ranked:
        if len(out) >= n_results:
            break
        add_one(r)
    return out[:n_results]


class MrDiceToolResult(TypedDict):
    # --- OPTIMADE MCP compatible keys ---
    output_dir: str
    cleaned_structures: List[SearchResult]
    n_found: int
    code: int
    message: str

    # --- MrDice legacy keys (keep backward compatible) ---
    returned: int
    fallback_level: int
    query_used: str
    results: List[SearchResult]

    # --- extra ---
    files: List[str]
    by_source: Dict[str, int]
    by_source_found: Dict[str, int]
    errors: Dict[str, str]


def parse_args():
    parser = argparse.ArgumentParser(description="MrDice Unified MCP Server")
    parser.add_argument("--port", type=int, default=50001, help="Server port (default: 50001)")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (default: MR_DICE_BOHRIUM_OUTPUT_DIR/mr_dice.log or ./mr_dice.log)",
    )
    try:
        # Use parse_known_args to avoid breaking other CLIs that import this module (e.g. `adk web`).
        args, _unknown = parser.parse_known_args()
        return args
    except SystemExit:
        class Args:
            port = 50001
            host = "0.0.0.0"
            log_level = "INFO"
            log_file = None
        return Args()


args = parse_args()

# Setup logger with file output
from .logger import setup_logger
import os

# Default log file path: use MR_DICE_BOHRIUM_OUTPUT_DIR if set, otherwise use current directory
if args.log_file is None:
    bohrium_output_dir = os.getenv("MR_DICE_BOHRIUM_OUTPUT_DIR")
    if bohrium_output_dir:
        base_dir = Path(bohrium_output_dir)
    else:
        base_dir = Path.cwd()

    # Use date-based filename by default
    date_tag = datetime.now().strftime("%Y%m%d")
    log_file = base_dir / f"mr_dice_{date_tag}.log"
else:
    log_file = Path(args.log_file)

logger = setup_logger(
    name="mrdice",
    level=args.log_level,
    log_file=log_file,
)
logger.info(f"Log file: {log_file.resolve()}")

# Also bind dp/mcp internal logs to the same handlers so you can see
# tool-call execution logs in the server console (not only uvicorn access logs).
try:
    _log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    for _name in [
        "dp",
        "dp.agent",
        "dp.agent.server",
        "dpdispatcher",
        "mcp",
        "mcp.server",
    ]:
        _l = logging.getLogger(_name)
        _l.setLevel(_log_level)
        _l.handlers.clear()
        for _h in logger.handlers:
            _l.addHandler(_h)
        _l.propagate = False
except Exception:
    # Don't block server startup if logging binding fails
    pass

# --- MCP transport auth (token) ---
# If MR_DICE_MCP_TOKEN is set, we expose public endpoint `/mcp` that requires:
#   - query param: ?token=...  (requested by some deployment platforms), OR
#   - header: Authorization: Bearer ...
#
# Implementation detail: FastMCP's Streamable HTTP endpoint path is configurable.
# When token auth is enabled, we mount the real MCP handler on an internal path
# and expose `/mcp` as a proxy route that performs token validation first.
MR_DICE_MCP_TOKEN = (os.getenv("MR_DICE_MCP_TOKEN") or "").strip()
MR_DICE_MCP_PUBLIC_PATH = (os.getenv("MR_DICE_MCP_PUBLIC_PATH") or "/mcp").strip() or "/mcp"
_internal_override = (os.getenv("MR_DICE_MCP_INTERNAL_PATH") or "").strip()
if MR_DICE_MCP_TOKEN and not _internal_override:
    # Generate an unguessable internal path so the public `/mcp` is the only practical entry.
    _h = hashlib.sha1(MR_DICE_MCP_TOKEN.encode("utf-8")).hexdigest()[:12]
    MR_DICE_MCP_INTERNAL_PATH = f"/__mrdice_mcp_{_h}"
else:
    MR_DICE_MCP_INTERNAL_PATH = _internal_override or "/__mrdice_mcp"

mcp = CalculationMCPServer(
    "MrDiceServer",
    port=args.port,
    host=args.host,
    streamable_http_path=(MR_DICE_MCP_INTERNAL_PATH if MR_DICE_MCP_TOKEN else MR_DICE_MCP_PUBLIC_PATH),
)

if MR_DICE_MCP_TOKEN:
    from mcp.server.fastmcp.server import StreamableHTTPASGIApp

    class _TokenAuthStreamableHttpProxy:
        """
        ASGI endpoint mounted at MR_DICE_MCP_PUBLIC_PATH.

        - Validates token from query param or Authorization header.
        - Forwards request to FastMCP Streamable HTTP session manager.
        """

        def __init__(self, token: str):
            self._token = token

        @staticmethod
        def _extract_token(scope: Scope) -> str | None:
            # 1) query param token=...
            try:
                qs = (scope.get("query_string") or b"").decode("utf-8", errors="ignore")
                token = (parse_qs(qs).get("token") or [None])[0]
                if token:
                    return str(token)
            except Exception:
                pass

            # 2) Authorization: Bearer <token>
            headers = scope.get("headers") or []
            for k, v in headers:
                if k.lower() == b"authorization":
                    try:
                        s = v.decode("utf-8", errors="ignore").strip()
                    except Exception:
                        s = ""
                    if s.lower().startswith("bearer "):
                        t = s[7:].strip()
                        return t or None
            return None

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            token = self._extract_token(scope)
            if token != self._token:
                body = json.dumps(
                    {"error": "unauthorized", "message": "Invalid or missing token"},
                    ensure_ascii=False,
                ).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json; charset=utf-8"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return

            # FastMCP creates the session manager lazily when the streamable HTTP app is built.
            # When we are called as a route inside that app, the session manager must exist.
            inner = StreamableHTTPASGIApp(mcp.mcp.session_manager)
            await inner(scope, receive, send)

    # Mount proxy route (public path) after the internal MCP route.
    # This route is only meaningful in streamable-http transport.
    mcp.mcp._custom_starlette_routes.append(
        Route(
            MR_DICE_MCP_PUBLIC_PATH,
            endpoint=_TokenAuthStreamableHttpProxy(MR_DICE_MCP_TOKEN),
            methods=["GET", "POST", "OPTIONS"],
            name="mcp_token_proxy",
        )
    )

# Keys whose values should be masked when printing env (e.g. API keys, secrets)
_ENV_MASK_KEYS = frozenset({
    "LLM_API_KEY", "MATERIALS_ACCESS_KEY",
    "OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET",
    "MR_DICE_MCP_TOKEN",
    "MR_DICE_MCP_INTERNAL_PATH",
})


def print_startup_env() -> None:
    """
    Print relevant environment variables to console at server startup.
    Masks sensitive values (API keys, secrets).
    """
    keys = [
        "LLM_PROVIDER", "LLM_MODEL", "LLM_API_BASE", "LLM_API_KEY", "LLM_DEBUG",
        "MR_DICE_DATA_DIR", "MR_DICE_BOHRIUM_OUTPUT_DIR", "MOFDB_SQL_DB_PATH",
        "BOHRIUM_USER_ID", "BOHRIUM_BASE_URL", "BOHRIUM_ACCESS_KEY", "BOHRIUM_PROJECT_ID",
        "MATERIALS_ACCESS_KEY", "MATERIALS_PROJECT_ID", "MATERIALS_SKU_ID",
        "OSS_ENABLED", "OSS_BUCKET_NAME", "OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_ENDPOINT",
        "DB_CORE_HOST", "BOHRIUM_CORE_HOST", "SERVER_URL",
        "MR_DICE_MCP_TOKEN", "MR_DICE_MCP_PUBLIC_PATH",
    ]
    print("=== MrDice server env ===")
    for k in keys:
        v = os.getenv(k)
        if v is None or v == "":
            print(f"  {k}= (unset)")
        elif k in _ENV_MASK_KEYS:
            print(f"  {k}= *** (set)")
        else:
            print(f"  {k}= {v}")
    print("=========================")


def _tag_from_text(text: str, max_len: int = 30) -> str:
    """
    Create a filesystem-safe short tag from arbitrary text.
    """
    t = (text or "").strip()
    if not t:
        return "query"
    t = t.replace('"', "").replace("'", "")
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^0-9A-Za-z_\-]+", "", t)
    if len(t) > max_len:
        t = t[:max_len]
    return t or "query"


def _build_mrdice_output_dir(query_used: str) -> Path:
    """
    Build a MrDice output directory path similar to OPTIMADE MCP servers.
    """
    base_dir = get_data_dir() / "materials_data_mrdice"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1((query_used or "").encode("utf-8")).hexdigest()[:8]
    tag = _tag_from_text(query_used)
    out_dir = base_dir / f"{tag}_{ts}_{short}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _collect_and_copy_result_files(
    *, results: List[SearchResult], output_dir: Path, output_format: str
) -> List[Path]:
    """
    Copy structure files into output_dir (best-effort) and return copied file paths.

    Returns List[Path] so that dp.agent's handle_output_artifacts can upload them
    to storage (e.g. Bohrium/OSS) and replace with URIs when storage is configured.
    """
    files: List[Path] = []
    for i, r in enumerate(results):
        src = (r.get("structure_file") or "").strip()
        if not src:
            continue
        src_path = Path(src)
        if not src_path.exists() or not src_path.is_file():
            continue

        # Build a stable filename
        suffix = src_path.suffix.lstrip(".") or (output_format or "cif")
        source = (r.get("source") or "mrdice").strip() or "mrdice"
        rid = (r.get("id") or "").strip()
        stem = f"{source}_{rid}_{i}" if rid else f"{source}_{i}"
        dst_path = output_dir / f"{stem}.{suffix}"

        try:
            shutil.copy2(src_path, dst_path)
            files.append(dst_path)
        except Exception:
            # best-effort only; do not fail the whole request
            continue
    return files


@mcp.tool()
async def fetch_structures_from_db(
    query: str,
    n_results: int = DEFAULT_N_RESULTS,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> MrDiceToolResult:
    """
    Unified search entry with complete preprocessing, parallel search, and postprocessing.
    
    Flow:
    1. Preprocessing: intent recognition -> parameter construction
    2. Parallel search: search multiple databases in parallel
    3. Postprocessing: ranking and response building
    """
    if not query or not query.strip():
        # Keep backward-compatible fields + OPTIMADE-like FetchResult keys
        resp = build_response(
            n_found=0,
            returned=0,
            fallback_level=0,
            query_used="",
            results=[],
        )
        resp.update(
            {
                "output_dir": _build_mrdice_output_dir("empty_query"),
                "cleaned_structures": [],
                "code": -1,
                "message": "Empty query",
            }
        )
        return resp

    n_results = normalize_n_results(n_results, DEFAULT_N_RESULTS, MAX_N_RESULTS)
    
    # === PREPROCESSING ===
    # Step 1: Intent recognition and parameter construction
    preprocessed = preprocess_query(query)
    material_type = preprocessed["material_type"]
    domain = preprocessed["domain"]
    filters = preprocessed["filters"]
    keywords = preprocessed["keywords"]
    expanded_query = preprocessed.get("expanded_query", query)
    target_databases = preprocessed.get("target_databases") or []
    
    # Build compact filter dict for logging (skip None and empty values).
    _empty = (None, {}, [], "")
    _effective = {k: v for k, v in filters.items() if v not in _empty}
    db_names = target_databases or ALL_DATABASE_NAMES

    logger.info(
        "Search: query=%s, dbs=%s, filters=%s",
        expanded_query or query,
        db_names,
        json.dumps(_effective, ensure_ascii=False),
    )

    # Resolve elements_options -> multiple queries, then merge (e.g. 过渡金属硫化物: S+Ti, S+V, S+Mo, ...)
    elements_options = filters.pop("elements_options", None)
    if elements_options and isinstance(elements_options, list):
        options = []
        for opt in elements_options[:8]:
            if isinstance(opt, list) and opt:
                options.append([str(x).strip() for x in opt if str(x).strip()])
        if options:
            elements_options = [o for o in options if o]
        else:
            elements_options = None
    if elements_options:
        filters["elements"] = filters.get("elements") or []

    # === SEARCH EXECUTION ===
    all_results: List[SearchResult] = []
    fallback_level = 0
    errors: Dict[str, str] = {}
    if elements_options:
        n_per = max(1, (n_results + len(elements_options) - 1) // len(elements_options))
        logger.info("Querying %s element options (n_per=%s): %s", len(elements_options), n_per, elements_options)
        try:
            async def _search_one_option(elem_list: List[str]):
                f = {**filters, "elements": elem_list}
                return await search_databases_parallel_with_errors(
                    db_names=db_names,
                    filters=f,
                    n_results=n_per,
                    output_format=output_format,
                )
            gathered = await asyncio.gather(*[_search_one_option(opt) for opt in elements_options])
            seen_keys: set = set()
            for db_results_i, errs_i in gathered:
                if errs_i:
                    for k, v in errs_i.items():
                        errors[f"{k}"] = errors.get(k, "") + ("; " if errors.get(k) else "") + v
                for _db_name, _results in db_results_i.items():
                    for r in _results:
                        key = (r.get("source") or "", r.get("id") or r.get("name") or "")
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_results.append(r)
            if all_results:
                logger.info("Merged %s results from %s element options", len(all_results), len(elements_options))
        except Exception as e:
            logger.error("Element-options search failed: %s", e)
            errors["search"] = str(e)
        filters["elements"] = elements_options[0]
    else:
        try:
            db_results, errors = await search_databases_parallel_with_errors(
                db_names=db_names,
                filters=filters,
                n_results=n_results,
                output_format=output_format,
            )
            if len(db_names) > 1:
                all_results = _merge_results_multi_db(db_results, db_names)
            else:
                for _db_name, _results in db_results.items():
                    all_results.extend(_results)
            if all_results:
                logger.info(f"Found {len(all_results)} results")
        except Exception as e:
            logger.error(f"Parallel search failed: {e}")
            errors = {"search": str(e)}

    # === FALLBACK: zero results -> relax to element-only filter and retry ===
    if len(all_results) == 0:
        relaxed_filters, relaxed_query = relax_to_element_only_filter(query, filters)
        if relaxed_filters and relaxed_filters.get("elements"):
            logger.info(
                "No results; retrying with element-only filter: elements=%s",
                relaxed_filters.get("elements"),
            )
            try:
                db_results_2, errors_2 = await search_databases_parallel_with_errors(
                    db_names=db_names,
                    filters=relaxed_filters,
                    n_results=n_results,
                    output_format=output_format,
                )
                if len(db_names) > 1:
                    all_results = _merge_results_multi_db(db_results_2, db_names)
                else:
                    for _db_name, _results in db_results_2.items():
                        all_results.extend(_results)
                if errors_2:
                    errors["relaxed_search"] = "; ".join(f"{k}: {v}" for k, v in errors_2.items())
                if all_results:
                    fallback_level = 1
                    filters = relaxed_filters
                    if relaxed_query:
                        expanded_query = relaxed_query
                    logger.info("Relaxed search found %s results", len(all_results))
            except Exception as e:
                logger.warning("Relaxed search failed: %s", e)

    # === POSTPROCESSING ===
    # Step 4: Rank and format results
    ranked = rank_results(
        all_results,
        formula=filters.get("formula") or "",
        space_group=str(filters.get("space_group") or ""),
        elements=filters.get("elements") or [],
        keywords=keywords,
    )
    if len(db_names) > 1:
        ranked = _take_n_results_with_sources(ranked, n_results, db_names)
    else:
        ranked = ranked[:n_results]

    def _count_by_source(items: List[SearchResult]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in items:
            src = (r.get("source") or "").strip() or "unknown"
            counts[src] = counts.get(src, 0) + 1
        return counts

    by_source = _count_by_source(ranked)
    by_source_found = _count_by_source(all_results)
    
    # ---- Build backward-compatible response ----
    resp = build_response(
        n_found=len(all_results),
        returned=len(ranked),
        fallback_level=fallback_level,
        query_used=expanded_query,
        results=ranked,
    )

    # ---- Add OPTIMADE-like FetchResult keys (for compatibility with :50004 tools) ----
    output_dir = _build_mrdice_output_dir(expanded_query)
    files = _collect_and_copy_result_files(results=ranked, output_dir=output_dir, output_format=output_format)

    manifest = {
        "mode": "fetch_structures_from_db",
        "query": query,
        "query_used": expanded_query,
        "n_results": n_results,
        "output_format": output_format,
        "n_found": len(all_results),
        "returned": len(ranked),
        "fallback_level": fallback_level,
        "by_source_found": by_source_found,
        "by_source": by_source,
        "errors": errors,
        "files": [str(p) for p in files],
        "results": ranked,
    }
    try:
        (output_dir / "summary.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    except Exception:
        pass

    # Return output_dir and files as Path/List[Path] so that dp.agent's
    # handle_output_artifacts can upload them to storage (Bohrium/OSS) and
    # replace with URIs when the agent is run with storage configured
    # (e.g. CalculationMCPToolset(storage=HTTPS_STORAGE)).
    resp.update(
        {
            "output_dir": output_dir,
            "cleaned_structures": ranked,
            "code": 0 if len(all_results) > 0 else -9999,
            "message": "Success" if len(all_results) > 0 else ("No results" if not errors else "No results (see errors)"),
            "files": files,
            "by_source_found": by_source_found,
            "by_source": by_source,
            "errors": errors,
        }
    )
    return resp


if __name__ == "__main__":
    print_startup_env()
    logger.info("Starting MrDice Unified MCP Server...")
    mcp.run(transport="streamable-http")
