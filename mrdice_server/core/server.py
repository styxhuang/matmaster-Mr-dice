import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from dp.agent.server import CalculationMCPServer

# Load environment variables from root .env file
env_path = Path.cwd() / ".env"
load_dotenv(env_path)

from .config import DEFAULT_N_RESULTS, DEFAULT_OUTPUT_FORMAT, MAX_N_RESULTS
from .postprocessor import DegradationRecord, degrade_filters, handle_search_error
from .preprocessor import preprocess_query
from ..search.ranker import rank_results
from ..search.router import normalize_n_results, select_databases
from ..models.schema import build_response, SearchResult
from ..search.searcher import search_databases_parallel


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
    Unified search entry with complete preprocessing, parallel search, and postprocessing.
    
    Flow:
    1. Preprocessing: intent recognition -> parameter construction
    2. Database selection: intelligent selection based on material type and filters
    3. Parallel search: search multiple databases in parallel
    4. Postprocessing: error handling, degradation, ranking, and response building
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
    
    # === PREPROCESSING ===
    # Step 1: Intent recognition and parameter construction
    preprocessed = preprocess_query(query)
    material_type = preprocessed["material_type"]
    domain = preprocessed["domain"]
    filters = preprocessed["filters"]
    keywords = preprocessed["keywords"]
    expanded_query = preprocessed.get("expanded_query", query)
    
    logging.info(
        f"Preprocessing: type={material_type}, domain={domain}, "
        f"filters={list(filters.keys())}"
    )
    
    # === DATABASE SELECTION ===
    # Step 2: Select databases based on material type, domain, and filters
    db_names = select_databases(material_type, domain, filters)
    
    # === SEARCH EXECUTION ===
    # Step 3: Search with degradation strategy
    all_results: List[SearchResult] = []
    fallback_level = 0
    degradation_record = DegradationRecord()
    max_attempts = 4
    
    for attempt in range(1, max_attempts + 1):
        fallback_level = attempt - 1
        attempt_filters = degrade_filters(filters, attempt)
        
        logging.info(f"Search attempt {attempt} with filters: {list(attempt_filters.keys())}")
        
        try:
            # Parallel search across selected databases
            db_results = await search_databases_parallel(
                db_names,
                attempt_filters,
                n_results,
                output_format,
            )
            
            # Collect all results
            for db_name, results in db_results.items():
                all_results.extend(results)
            
            # Record attempt
            degradation_record.add_attempt(
                attempt=attempt,
                filters=attempt_filters,
                databases=db_names,
                results_count=len(all_results),
            )
            
            # If we have results, break
            if all_results:
                logging.info(f"Found {len(all_results)} results on attempt {attempt}")
                break
                
        except Exception as e:
            # Handle errors: classify and potentially correct parameters
            corrected_params, should_retry = handle_search_error(
                query,
                {"filters": attempt_filters, "keywords": keywords},
                e,
                all_results,
                degradation_record,
            )
            
            if corrected_params and should_retry:
                # Retry with corrected parameters
                filters = corrected_params.get("filters", filters)
                keywords = corrected_params.get("keywords", keywords)
                attempt_filters = filters
                logging.info("Retrying with corrected parameters")
                continue
            
            if not should_retry:
                # Don't retry for logic/network errors
                logging.error(f"Search failed with non-retryable error: {e}")
                break
            
            # Continue to next degradation level
            logging.warning(f"Attempt {attempt} failed, trying degradation level {attempt + 1}")
    
    # === POSTPROCESSING ===
    # Step 4: Rank and format results
    ranked = rank_results(
        all_results,
        formula=filters.get("formula") or "",
        space_group=str(filters.get("space_group") or ""),
        elements=filters.get("elements") or [],
        keywords=keywords,
    )
    
    ranked = ranked[:n_results]
    
    # Log degradation record if debug mode
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f"Degradation record: {degradation_record.to_dict()}")
    
    return build_response(
        n_found=len(all_results),
        returned=len(ranked),
        fallback_level=fallback_level,
        query_used=expanded_query,
        results=ranked,
    )


if __name__ == "__main__":
    logging.info("Starting MrDice Unified MCP Server...")
    mcp.run(transport="sse")
