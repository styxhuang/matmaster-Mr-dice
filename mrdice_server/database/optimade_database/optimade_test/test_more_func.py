import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel, ValidationError
from optimade.client import OptimadeClient

from utils import save_structures  # make sure utils.py is in the same dir

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROVIDERS = {
    "alexandria", "cmr", "mp", "mpds", "nmd",
    "odbx", "omdb", "oqmd", "jarvis"
}

# === RESULT TYPE ===
class FetchResult(TypedDict):
    output_dir: Path
    files: List[str]
    providers_used: List[str]
    filter: str
    warnings: List[str]

# === Query schema (elements-only) ===
Format = Literal["cif", "json"]

class QueryParams(BaseModel):
    elements_all: Optional[List[str]] = None
    elements_any: Optional[List[str]] = None
    elements_only: Optional[List[str]] = None

    as_format: Format = "cif"
    max_results_per_provider: int = 2
    providers: Optional[List[str]] = None

# === Filter builder ===
def build_filter(q: "QueryParams") -> str:
    parts = []
    if q.elements_all:
        parts.append('elements HAS ALL ' + ', '.join(f'"{e}"' for e in q.elements_all))
    if q.elements_any:
        parts.append('elements HAS ANY ' + ', '.join(f'"{e}"' for e in q.elements_any))
    if q.elements_only:
        parts.append('elements HAS ONLY ' + ', '.join(f'"{e}"' for e in q.elements_only))
    return " AND ".join(parts) if parts else 'elements HAS ANY "Si"'

# === Retrieval function ===
def fetch_structures_advanced(query: dict) -> FetchResult:
    try:
        q = QueryParams(**query)
    except ValidationError as e:
        logging.error(f"[adv] Query validation failed: {e}")
        return {
            "output_dir": Path(),
            "files": [],
            "providers_used": [],
            "filter": "",
            "warnings": [f"validation_error: {e}"],
        }

    filter_str = build_filter(q)
    used_providers = set(q.providers) if q.providers else DEFAULT_PROVIDERS
    logging.info(f"[adv] providers={used_providers} filter={filter_str}")

    try:
        client = OptimadeClient(
            include_providers=used_providers,
            max_results_per_provider=q.max_results_per_provider
        )
        results = client.get(filter=filter_str)
    except Exception as e:
        msg = f"[adv] fetch failed: {e}"
        logging.error(msg)
        return {
            "output_dir": Path(),
            "files": [],
            "providers_used": sorted(list(used_providers)),
            "filter": filter_str,
            "warnings": [msg],
        }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_folder = BASE_OUTPUT_DIR / f"elements_query_{ts}"
    files, warns, providers_seen = save_structures(
        results, out_folder, q.max_results_per_provider, as_cif=(q.as_format == "cif")
    )

    return {
        "output_dir": out_folder,
        "files": files,
        "providers_used": sorted(list(set(providers_seen))),
        "filter": filter_str,
        "warnings": warns,
    }

# === MAIN for testing ===
if __name__ == "__main__":
    logging.basicConfig(level="INFO")

    # Demo 1: elements_all
    res1 = fetch_structures_advanced({
        "elements_all": ["Al", "O", "Mg"],
        "as_format": "cif",
        "max_results_per_provider": 3
    })
    print("\n[Demo 1] elements_all=Al,O,Mg → CIF")
    print(json.dumps(res1, indent=2, default=str))

    # Demo 2: elements_any
    res2 = fetch_structures_advanced({
        "elements_any": ["Al", "O"],
        "as_format": "json",
        "max_results_per_provider": 1
    })
    print("\n[Demo 2] elements_any=Al,O → JSON")
    print(json.dumps(res2, indent=2, default=str))

    # Demo 3: elements_only, custom providers
    res3 = fetch_structures_advanced({
        "elements_only": ["C"],
        "as_format": "cif",
        "providers": ["mp", "jarvis"],
        "max_results_per_provider": 2
    })
    print("\n[Demo 3] elements_only=C → CIF from MP & JARVIS")
    print(json.dumps(res3, indent=2, default=str))