import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from dp.agent.server import CalculationMCPServer

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from .config import DEFAULT_N_RESULTS, DEFAULT_OUTPUT_FORMAT, MAX_N_RESULTS
from .llm_expand import expand_query
from .ranker import rank_results
from .router import degrade_filters, normalize_n_results, plan_routes
from .schema import build_response, SearchResult


def _get_bohrium_retriever():
    """
    Lazy import and initialization of Bohrium retriever.
    """
    from .retrievers.bohriumpublic import BohriumPublicRetriever

    return BohriumPublicRetriever()


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
    try:
        return parser.parse_args()
    except SystemExit:
        class Args:
            port = 50001
            host = "0.0.0.0"
            log_level = "INFO"
        return Args()


args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("MrDiceServer", port=args.port, host=args.host)


@mcp.tool()
async def mrdice_search(
    query: str,
    n_results: int = DEFAULT_N_RESULTS,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> Dict[str, Any]:
    """
    Unified search entry. This is a scaffold version without DB wiring.
    """
    if not query or not query.strip():
        return build_response(
            n_found=0,
            returned=0,
            fallback_level=0,
            query_used="",
            results=[],
        )

    n_results = normalize_n_results(n_results, DEFAULT_N_RESULTS, MAX_N_RESULTS)

    expanded = expand_query(query)
    filters = expanded.get("filters") or {}
    material_type = expanded.get("material_type") or "unknown"
    keywords = expanded.get("keywords") or []

    routes = plan_routes(material_type)
    all_results: List[SearchResult] = []
    fallback_level = 0

    # TODO: wire retrievers per route
    # For now, we only simulate the retry loop and return empty results.
    for attempt in [1, 2, 3]:
        fallback_level = attempt - 1
        attempt_filters = degrade_filters(filters, attempt)
        for route in routes:
            if route == "bohriumpublic":
                retriever = _get_bohrium_retriever()
                all_results.extend(
                    retriever.fetch(attempt_filters, n_results, output_format)
                )
        if all_results:
            break

    ranked = rank_results(
        all_results,
        formula=filters.get("formula") or "",
        space_group=str(filters.get("space_group") or ""),
        elements=filters.get("elements") or [],
        keywords=keywords,
    )

    ranked = ranked[:n_results]
    return build_response(
        n_found=len(all_results),
        returned=len(ranked),
        fallback_level=fallback_level,
        query_used=query,
        results=ranked,
    )


if __name__ == "__main__":
    logging.info("Starting MrDice Unified MCP Server...")
    mcp.run(transport="sse")
