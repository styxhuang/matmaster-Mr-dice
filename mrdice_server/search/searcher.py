"""
Search execution module: parallel database searching.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..retrievers.base import Retriever
from ..retrievers.bohriumpublic import BohriumPublicRetriever
from ..models.schema import SearchResult


def _get_retriever(db_name: str) -> Optional[Retriever]:
    """
    Get retriever instance for database name.
    
    Returns:
        Retriever instance or None if not available
    """
    if db_name == "bohriumpublic":
        return BohriumPublicRetriever()
    # TODO: Add other retrievers
    # elif db_name == "mofdb":
    #     return MofdbRetriever()
    # elif db_name == "mofdbsql":
    #     return MofdbSqlRetriever()
    # elif db_name == "openlam":
    #     return OpenlamRetriever()
    # elif db_name == "optimade":
    #     return OptimadeRetriever()
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
    if not db_names:
        return {}
    
    # Create tasks for parallel execution
    tasks = [
        _search_single_db(db_name, filters, n_results, output_format)
        for db_name in db_names
    ]
    
    # Execute all searches in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Collect results
    db_results: Dict[str, List[SearchResult]] = {}
    for result in results:
        if isinstance(result, Exception):
            logging.error(f"Task failed with exception: {result}")
            continue
        
        db_name, search_results, error = result
        if error:
            logging.warning(f"Database {db_name} search failed: {error}")
        db_results[db_name] = search_results
    
    return db_results

