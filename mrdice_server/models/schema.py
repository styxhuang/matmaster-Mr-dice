from typing import Any, Dict, List, Optional, TypedDict


class SearchResult(TypedDict):
    name: Optional[str]
    structure_file: Optional[str]
    formula: Optional[str]
    elements: List[str]
    space_group: Optional[str]
    n_atoms: Optional[int]
    band_gap: Optional[float]
    formation_energy: Optional[float]
    source: Optional[str]
    id: Optional[str]


class SearchResponse(TypedDict):
    n_found: int
    returned: int
    fallback_level: int
    query_used: str
    results: List[SearchResult]


def normalize_result(
    *,
    name: Optional[str] = None,
    structure_file: Optional[str] = None,
    formula: Optional[str] = None,
    elements: Optional[List[str]] = None,
    space_group: Optional[str] = None,
    n_atoms: Optional[int] = None,
    band_gap: Optional[float] = None,
    formation_energy: Optional[float] = None,
    source: Optional[str] = None,
    id: Optional[str] = None,
) -> SearchResult:
    return {
        "name": name or None,
        "structure_file": structure_file or None,
        "formula": formula or None,
        "elements": elements or [],
        "space_group": space_group or None,
        "n_atoms": n_atoms,
        "band_gap": band_gap,
        "formation_energy": formation_energy,
        "source": source or None,
        "id": id or None,
    }


def build_response(
    *,
    n_found: int,
    returned: int,
    fallback_level: int,
    query_used: str,
    results: List[SearchResult],
) -> SearchResponse:
    return {
        "n_found": n_found,
        "returned": returned,
        "fallback_level": fallback_level,
        "query_used": query_used,
        "results": results,
    }
