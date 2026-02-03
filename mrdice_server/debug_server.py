"""
Debug server using FastAPI for local development and testing.
Run with: uvicorn mrdice_server.debug_server:app --reload --host 0.0.0.0 --port 50001
"""
import logging
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from .config import DEFAULT_N_RESULTS, DEFAULT_OUTPUT_FORMAT, MAX_N_RESULTS
from .llm_expand import expand_query
from .ranker import rank_results
from .router import degrade_filters, normalize_n_results, plan_routes
from .schema import build_response, SearchResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MrDice Debug Server",
    description="Debug interface for MrDice materials search",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_bohrium_retriever():
    """
    Lazy import and initialization of Bohrium retriever.
    """
    from .retrievers.bohriumpublic import BohriumPublicRetriever

    return BohriumPublicRetriever()


class SearchRequest(BaseModel):
    """Search request model."""

    query: str = Field(..., description="Search query in natural language")
    n_results: int = Field(
        default=DEFAULT_N_RESULTS,
        ge=1,
        le=MAX_N_RESULTS,
        description=f"Number of results to return (1-{MAX_N_RESULTS})",
    )
    output_format: str = Field(
        default=DEFAULT_OUTPUT_FORMAT,
        description="Output format: 'cif' or 'json'",
    )


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "MrDice Debug Server"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/search", response_model=Dict[str, Any])
async def search(request: SearchRequest) -> Dict[str, Any]:
    """
    Unified search endpoint for materials database.
    """
    try:
        query = request.query.strip()
        if not query:
            return build_response(
                n_found=0,
                returned=0,
                fallback_level=0,
                query_used="",
                results=[],
            )

        n_results = normalize_n_results(request.n_results, DEFAULT_N_RESULTS, MAX_N_RESULTS)
        output_format = request.output_format

        logger.info(f"Processing search query: {query}")

        # Expand query using LLM
        expanded = expand_query(query)
        filters = expanded.get("filters") or {}
        material_type = expanded.get("material_type") or "unknown"
        keywords = expanded.get("keywords") or []

        logger.info(f"Expanded query - material_type: {material_type}, filters: {filters}")

        # Plan routes based on material type
        routes = plan_routes(material_type)
        logger.info(f"Planned routes: {routes}")

        all_results: list[SearchResult] = []
        fallback_level = 0

        # Retry loop with degraded filters
        for attempt in [1, 2, 3]:
            fallback_level = attempt - 1
            attempt_filters = degrade_filters(filters, attempt)
            logger.info(f"Attempt {attempt} with filters: {attempt_filters}")

            for route in routes:
                if route == "bohriumpublic":
                    retriever = _get_bohrium_retriever()
                    results = retriever.fetch(attempt_filters, n_results, output_format)
                    all_results.extend(results)
                    logger.info(f"Route {route} returned {len(results)} results")

            if all_results:
                logger.info(f"Found {len(all_results)} results at attempt {attempt}")
                break

        # Rank results
        ranked = rank_results(
            all_results,
            formula=filters.get("formula") or "",
            space_group=str(filters.get("space_group") or ""),
            elements=filters.get("elements") or [],
            keywords=keywords,
        )

        ranked = ranked[:n_results]

        response = build_response(
            n_found=len(all_results),
            returned=len(ranked),
            fallback_level=fallback_level,
            query_used=query,
            results=ranked,
        )

        logger.info(f"Returning {len(ranked)} results")
        return response

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/debug/expand")
async def debug_expand(query: str):
    """
    Debug endpoint to see how a query is expanded.
    """
    try:
        expanded = expand_query(query)
        return {
            "query": query,
            "expanded": expanded,
        }
    except Exception as e:
        logger.error(f"Expand error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Expand failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mrdice_server.debug_server:app",
        host="0.0.0.0",
        port=50001,
        reload=True,
        log_level="info",
    )

