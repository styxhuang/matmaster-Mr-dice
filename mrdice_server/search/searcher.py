"""
Search execution module: parallel database searching.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..retrievers.base import Retriever
from ..retrievers.bohriumpublic import BohriumPublicRetriever
from ..retrievers.mofdbsql import MofdbSqlRetriever
from ..retrievers.openlam import OpenlamRetriever
from ..retrievers.optimade import OptimadeRetriever
from ..models.schema import SearchResult

# All databases to be searched in parallel (no pre-selection)
ALL_DATABASE_NAMES: List[str] = [
    "bohriumpublic",
    "mofdbsql",
    "openlam",
    "optimade",
]


def _get_retriever(db_name: str) -> Optional[Retriever]:
    """
    Get retriever instance for database name.
    
    Returns:
        Retriever instance or None if not available
    """
    if db_name == "bohriumpublic":
        return BohriumPublicRetriever()
    elif db_name == "mofdbsql":
        return MofdbSqlRetriever()
    elif db_name == "openlam":
        return OpenlamRetriever()
    elif db_name == "optimade":
        return OptimadeRetriever()
    return None


async def _search_single_db(
    db_name: str,
    filters: Dict[str, Any],
    n_results: int,
    output_format: str,
) -> Tuple[str, List[SearchResult], Optional[Exception]]:
    """
    Search a single database asynchronously.
    
    Returns:
        Tuple of (db_name, results, error)
    """
    try:
        retriever = _get_retriever(db_name)
        if not retriever:
            logging.warning(f"Retriever not available for {db_name}")
            return db_name, [], None
        
        # Run synchronous fetch in executor
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            retriever.fetch,
            filters,
            n_results,
            output_format,
        )
        return db_name, results, None
    except Exception as e:
        logging.error(f"Error searching {db_name}: {e}")
        return db_name, [], e


async def search_databases_parallel(
    db_names: List[str],
    filters: Dict[str, Any],
    n_results: int,
    output_format: str,
) -> Dict[str, List[SearchResult]]:
    """
    Search multiple databases in parallel.
    
    Args:
        db_names: List of database names to search
        filters: Search filters
        n_results: Number of results per database
        output_format: Output format (cif, json, etc.)
    
    Returns:
        Dict mapping database names to their results
    """
    db_results, _db_errors = await search_databases_parallel_with_errors(
        db_names=db_names,
        filters=filters,
        n_results=n_results,
        output_format=output_format,
    )
    return db_results


async def search_databases_parallel_with_errors(
    *,
    db_names: List[str],
    filters: Dict[str, Any],
    n_results: int,
    output_format: str,
) -> Tuple[Dict[str, List[SearchResult]], Dict[str, str]]:
    """
    Search multiple databases in parallel and return both results and errors.

    Returns:
        (db_results, db_errors)
        - db_results maps db_name -> results (possibly empty)
        - db_errors maps db_name -> error message (only for failed DBs)
    """
    if not db_names:
        return {}, {}

    tasks = [
        _search_single_db(db_name, filters, n_results, output_format)
        for db_name in db_names
    ]
    gathered = await asyncio.gather(*tasks, return_exceptions=True)

    db_results: Dict[str, List[SearchResult]] = {}
    db_errors: Dict[str, str] = {}
    for item in gathered:
        if isinstance(item, Exception):
            logging.error(f"Task failed with exception: {item}")
            continue

        db_name, search_results, error = item
        db_results[db_name] = search_results
        if error:
            db_errors[db_name] = str(error)

    return db_results, db_errors

