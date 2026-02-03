from typing import Any, Dict, List, Tuple


def _count_element_overlap(target: List[str], candidate: List[str]) -> int:
    tset = set([e for e in target if e])
    cset = set([e for e in candidate if e])
    return len(tset & cset)


def _keyword_overlap_score(keywords: List[str], text: str) -> int:
    if not keywords or not text:
        return 0
    text_lower = text.lower()
    return sum(1 for k in keywords if k.lower() in text_lower)


def score_result(
    result: Dict[str, Any],
    *,
    formula: str = "",
    space_group: str = "",
    elements: List[str] = None,
    keywords: List[str] = None,
) -> int:
    elements = elements or []
    keywords = keywords or []
    score = 0

    if formula and result.get("formula") == formula:
        score += 2
    if space_group and result.get("space_group") == space_group:
        score += 2

    score += _count_element_overlap(elements, result.get("elements") or [])

    name = result.get("name") or ""
    score += _keyword_overlap_score(keywords, name)
    score += _keyword_overlap_score(keywords, result.get("formula") or "")

    return score


def rank_results(
    results: List[Dict[str, Any]],
    *,
    formula: str = "",
    space_group: str = "",
    elements: List[str] = None,
    keywords: List[str] = None,
) -> List[Dict[str, Any]]:
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for r in results:
        scored.append((score_result(
            r,
            formula=formula or "",
            space_group=space_group or "",
            elements=elements or [],
            keywords=keywords or [],
        ), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]
