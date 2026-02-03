import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
import hashlib
from anyio import to_thread

from optimade.client import OptimadeClient
from dp.agent.server import CalculationMCPServer

from utils import *

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROVIDERS = {
    # "aflow",
    "alexandria",
    # "aiida",
    # "ccdc",
    # "ccpnc",
    "cmr",
    "cod",
    # "httk",
    "jarvis",
    "matcloud",
    "matterverse",
    "mcloud",
    "mcloudarchive",
    "mp",
    "mpdd",
    "mpds",
    # "mpod",
    "nmd",
    "odbx",
    "omdb",
    "oqmd",
    # "optimade",
    # "optimake",
    # "pcod",
    # "psdi",
    "tcod",
    "twodmatpedia",
}


# === RESULT TYPE ===
Format = Literal["cif", "json"]

class FetchResult(TypedDict):
    output_dir: Path
    files: List[Path]
    # providers_used: List[str]
    # filter: str
    # warnings: List[str]

# === TOOL: RAW filter fetch ===
def fetch_structures_with_filter(
    filter: str,
    as_format: Format = "cif",
    max_results_per_provider: int = 2,
    providers: Optional[List[str]] = None,
) -> FetchResult:
    """
    Fetch crystal structures from OPTIMADE databases using a raw filter string.

    This function passes the provided OPTIMADE filter directly to all chosen providers
    (or the default set if none are specified). The filter can use any supported 
    OPTIMADE properties and logical operators, e.g.:
        - elements HAS ALL "Al","O","Mg"
        - elements HAS ONLY "Si","O"
        - elements HAS ALL "Al","O","Mg" AND nelements=3
        - chemical_formula_reduced="O2Si"
        - chemical_formula_descriptive CONTAINS "H2O"
        - chemical_formula_anonymous="A2B" AND NOT (elements HAS ANY "Na")

    Parameters
    ----------
    filter : str
        An OPTIMADE filter expression. Supports all valid syntax:
        - Property filters (elements, nelements, chemical_formula_reduced, etc.)
        - Logical operators: AND, OR, NOT (parentheses for grouping)
        - String equality/contains and numeric comparisons
    as_format : {"cif","json"}, optional
        Output format of saved structures.
        "cif"  → Crystallographic Information File (default)
        "json" → Raw OPTIMADE structure JSON
    max_results_per_provider : int, optional
        Maximum number of results to retrieve from each provider (default: 2).
    providers : list[str], optional
        List of OPTIMADE provider keys to query. If omitted, uses:
        {"aflow","alexandria","cmr","cod","jarvis","matcloud","matterverse","mcloud","mcloudarchive","mp","mpdd","mpds","mpod","nmd","odbx","omdb","oqmd","tcod","twodmatpedia"}
    Returns
    -------
    FetchResult
        {
          "output_dir": Path to the folder with saved results,
          "files": List of saved structure files,
          "providers_used": Providers that returned results,
          "filter": The filter string used,
          "warnings": Any error or warning messages
        }
    """
    filt = (filter or "").strip()
    if not filt:
        msg = "[raw] empty filter string"
        logging.error(msg)
        return {
            "output_dir": Path(),
            "files": [],
            "providers_used": [],
            "filter": "",
            "warnings": [msg],
        }
    
    used_providers = set(providers) if providers else DEFAULT_PROVIDERS
    logging.info(f"[raw] providers={used_providers} filter={filt}")

    try:
        client = OptimadeClient(
            include_providers=used_providers,
            max_results_per_provider=max_results_per_provider,
            http_timeout=60.0 
        )
        results = client.get(filter=filt)
    except Exception as e:
        msg = f"[raw] fetch failed: {e}"
        logging.error(msg)
        return {
            "output_dir": Path(),
            "files": [],
            "providers_used": sorted(list(used_providers)),
            "filter": filt,
            "warnings": [msg],
        }

    # timestamped folder + short hash of filter for traceability
    tag = filter_to_tag(filt)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(filt.encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short}"

    files, warns, providers_seen = save_structures(
        results, out_folder, max_results_per_provider, as_format == "cif"
    )

    # manifest (handy for downstream)
    manifest = {
        "filter": filt,
        "providers_requested": sorted(list(used_providers)),
        "providers_seen": providers_seen,
        "files": files,
        "warnings": warns,
        "format": as_format,
        "max_results_per_provider": max_results_per_provider,
    }
    (out_folder / "summary.json").write_text(json.dumps(manifest, indent=2))

    return {
        "output_dir": out_folder,
        "files": files,
        # "providers_used": sorted(list(set(providers_seen))),
        # "filter": filt,
        # "warnings": warns,
    }


if __name__ == "__main__":
    # gamma-TiAl (L10, space group 123)
    gamma_tial_filter = (
        'elements HAS ALL "H" '
    )

    result = fetch_structures_with_filter(
            filter=gamma_tial_filter,
            as_format="json",
            max_results_per_provider=1,
    )
    print("=== GAMMA-TiAl (L10) ===")
    print("Filter:", gamma_tial_filter)
    print("Output dir:", result["output_dir"])
    print("Files:", result["files"])

