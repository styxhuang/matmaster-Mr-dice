"""Search module: routing, searching, and ranking."""
from .ranker import rank_results, score_result
from .router import normalize_n_results, plan_routes, select_databases
from .searcher import ALL_DATABASE_NAMES, search_databases_parallel

__all__ = [
    "ALL_DATABASE_NAMES",
    "search_databases_parallel",
    "select_databases",
    "plan_routes",
    "normalize_n_results",
    "rank_results",
    "score_result",
]

