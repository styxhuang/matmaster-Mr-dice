from typing import Any, Dict, List, Protocol

from ..models.schema import SearchResult


class Retriever(Protocol):
    def fetch(self, filters: Dict[str, Any], n_results: int, output_format: str) -> List[SearchResult]:
        ...
