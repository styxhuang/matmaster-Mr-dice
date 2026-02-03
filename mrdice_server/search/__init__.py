"""Search module: routing, searching, and ranking."""
from .ranker import rank_results, score_result
from .router import normalize_n_results, plan_routes, select_databases
from .searcher import search_databases_parallel

__all__ = [
    "search_databases_parallel",
    "select_databases",
    "plan_routes",
    "normalize_n_results",
    "rank_results",
    "score_result",
]

