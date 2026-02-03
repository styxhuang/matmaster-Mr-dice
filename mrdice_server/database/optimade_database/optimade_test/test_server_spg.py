import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
import hashlib
from anyio import to_thread
import asyncio

from optimade.client import OptimadeClient
from dp.agent.server import CalculationMCPServer

from utils import *

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)



# === RESULT TYPE ===
class FetchResult(TypedDict):
    output_dir: Path
    files: List[Path]
    # providers_used: List[str]
    # filter: str
    # warnings: List[str]


async def fetch_structures_with_filter(
    filter: str,
    as_format: Literal["cif", "json"] = "cif",
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
            http_timeout=25.0 
        )
        results = await to_thread.run_sync(lambda: client.get(filter=filt))
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

    files, warns, providers_seen = await to_thread.run_sync(
        save_structures,
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
    }




async def fetch_structures_with_spg(
    base_filter: Optional[str],
    spg_number: int,
    as_format: Literal["cif", "json"] = "cif",
    max_results_per_provider: int = 3,
    providers: Optional[List[str]] = None,
) -> FetchResult:

    base_filter = (base_filter or "").strip()
    used_providers = set(providers) if providers else DEFAULT_SPG_PROVIDERS

    spg_filters = get_spg_filter_map(spg_number, used_providers)
    filters = build_provider_filters(base_filter, spg_filters)
    if not filters:
        logging.warning("[spg] no provider-specific space-group clause available")
        return {"output_dir": Path(), "files": []}

    async def _query_one(provider: str, clause: str) -> dict:
        logging.info(f"[spg] {provider}: {clause}")
        try:
            client = OptimadeClient(
                include_providers={provider},
                max_results_per_provider=max_results_per_provider,
                http_timeout=25.0,
            )
            # client.get is blocking → run in worker thread
            return await to_thread.run_sync(lambda: client.get(filter=clause))
        except Exception as e:
            logging.error(f"[spg] fetch failed for {provider}: {e}")
            return {"structures": {}}

    # fan out per provider
    results_list = await asyncio.gather(*[
        _query_one(p, clause) for p, clause in filters.items()
    ])

    tag = filter_to_tag(f"{base_filter} AND spg={spg_number}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(f"{base_filter}|spg={spg_number}".encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short}"

    all_files: List[str] = []
    all_warnings: List[str] = []
    all_providers: List[str] = []
    for res in results_list:
        files, warns, providers_seen = await to_thread.run_sync(
            save_structures,
            res, out_folder, max_results_per_provider, as_format == "cif"
        )
        all_files.extend(files)
        all_warnings.extend(warns)
        all_providers.extend(providers_seen)

    # optional manifest (handy for debugging)
    manifest = {
        "base_filter": base_filter,
        "spg_number": spg_number,
        "providers_requested": sorted(list(used_providers)),
        "providers_seen": all_providers,
        "files": all_files,
        "warnings": all_warnings,
        "format": as_format,
        "max_results_per_provider": max_results_per_provider,
        "per_provider_filters": filters, 
    }
    (out_folder / "summary.json").write_text(json.dumps(manifest, indent=2))

    return {
        "output_dir": out_folder,
        "files": all_files,
    }


# === TOOL: band gap (range) fetch ===
async def fetch_structures_with_bandgap(
    base_filter: Optional[str],
    min_bg: Optional[float] = None,
    max_bg: Optional[float] = None,
    as_format: Literal["cif", "json"] = "json",
    max_results_per_provider: int = 2,
    providers: Optional[List[str]] = None,
) -> FetchResult:
    """
    Fetch structures constrained by band gap range (per-provider property names),
    executed in parallel across providers.

    Args
    ----
    base_filter : str | None
        Common OPTIMADE filter (e.g., elements/chemistry) applied to all providers.
    min_bg, max_bg : float | None
        Band gap range in eV (open-ended allowed, e.g., min only or max only).
    as_format : "cif" | "json"
        Output format of saved files (default: "cif").
    max_results_per_provider : int
        Max results to keep per provider when saving.
    providers : list[str] | None
        Providers to query; if None, uses DEFAULT_BG_PROVIDERS.

    Returns
    -------
    FetchResult : { "output_dir": Path, "files": List[Path] }
    """
    base = (base_filter or "").strip()
    used = set(providers) if providers else DEFAULT_BG_PROVIDERS

    # Build per-provider bandgap clause, then combine with base
    bg_map = get_bandgap_filter_map(min_bg, max_bg, used)
    filters = build_provider_filters(base, bg_map)

    if not filters:
        logging.warning("[bandgap] no provider-specific band-gap clause available")
        return {"output_dir": Path(), "files": []}

    async def _query_one(provider: str, clause: str) -> dict:
        logging.info(f"[bandgap] {provider}: {clause}")
        try:
            client = OptimadeClient(
                include_providers={provider},
                max_results_per_provider=max_results_per_provider,
                http_timeout=25.0,
            )
            # client.get blocks → run in thread
            return await to_thread.run_sync(lambda: client.get(filter=clause))
        except Exception as e:
            logging.error(f"[bandgap] fetch failed for {provider}: {e}")
            return {"structures": {}}

    # Parallel fan-out
    results_list = await asyncio.gather(
        *[_query_one(p, clause) for p, clause in filters.items()]
    )

    # Output folder tag
    tag = filter_to_tag(f"{base} AND bandgap[{min_bg},{max_bg}]")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(f"{base}|bg={min_bg}:{max_bg}".encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short}"

    # Save all results together (same folder), collect manifest info
    all_files: List[str] = []
    all_warnings: List[str] = []
    all_providers: List[str] = []

    for res in results_list:
        files, warns, providers_seen = await to_thread.run_sync(
            save_structures,
            res, out_folder, max_results_per_provider, as_format == "cif"
        )
        all_files.extend(files)
        all_warnings.extend(warns)
        all_providers.extend(providers_seen)

    manifest = {
        "base_filter": base,
        "band_gap_min": min_bg,
        "band_gap_max": max_bg,
        "providers_requested": sorted(list(used)),
        "providers_seen": all_providers,
        "files": all_files,
        "warnings": all_warnings,
        "format": as_format,
        "max_results_per_provider": max_results_per_provider,
        "per_provider_filters": filters,
    }
    (out_folder / "summary.json").write_text(json.dumps(manifest, indent=2))

    return {
        "output_dir": out_folder,
        "files": all_files,
    }

output1 = asyncio.run(fetch_structures_with_spg(base_filter='chemical_formula_reduced=\"FeO\"', spg_number=225, as_format='json'))
print(output1)

# output2 = asyncio.run(fetch_structures_with_bandgap(base_filter='chemical_formula_reduced=FeO', min_bg=1.0, max_bg=2.0, as_format='json'))
# print(output2)

'''    "cod": "(chemical_formula_reduced=\"FeO\") AND (_cod_sg=\"F m - 3 m\")",
    "tcod": "(chemical_formula_reduced=\"FeO\") AND (_tcod_sg=\"F m - 3 m\")",
    "mpdd": "(chemical_formula_reduced=\"FeO\") AND (_mpdd_spacegroupn=225)",
    "odbx": "(chemical_formula_reduced=\"FeO\") AND (_gnome_space_group_it_number=225)",
    "alexandria": "(chemical_formula_reduced=\"FeO\") AND (_alexandria_space_group=225)",
    "nmd": "(chemical_formula_reduced=\"FeO\") AND (_nmd_dft_spacegroup=225)",
    "oqmd": "(chemical_formula_reduced=\"FeO\") AND (_oqmd_spacegroup=\"Fm-3m\")"'''