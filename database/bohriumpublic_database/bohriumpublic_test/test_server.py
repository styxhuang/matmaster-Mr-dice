import argparse
import logging
import json
import hashlib
import os
import sys
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
from anyio import to_thread
import asyncio
import requests

from dp.agent.server import CalculationMCPServer
from dotenv import load_dotenv

from utils import *

load_dotenv()

# === Output format type ===
Format = Literal["json", "cif"]

# === Result return type ===
class FetchResult(TypedDict):
    output_dir: Path
    cleaned_structures: List[dict]
    n_found: int
    code: int
    message: str


BASE_OUTPUT_DIR = Path("materials_data_bohriumpublic")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_bohrium_crystals(
    formula: Optional[str] = None,
    elements: Optional[List[str]] = None,
    match_mode: int = 1,
    spacegroup_number: Optional[int] = None, 
    atom_count_range: Optional[List[str]] = None,
    predicted_formation_energy_range: Optional[List[str]] = None,
    band_gap_range: Optional[List[str]] = None,
    n_results: int = 10,
    output_formats: List[Format] = ["cif"]
) -> FetchResult:
    """
    📦 Fetch crystal structures from the Bohrium public database.

    🔍 Features:
    -----------------------------------
    - Supports filtering by formula, elements, space group, atom count, formation energy, band gap.
    - Saves structures in `.cif` and/or `.json` formats.
    - Automatically creates a tagged output folder and manifest.

    🧩 Arguments:
    -----------------------------------
    formula : str, optional
        Formula keyword (fuzzy or exact depending on match_mode).
    elements : list of str, optional
        Required elements.
    match_mode : int
        0 = fuzzy match, 1 = exact match (only effective with formula/elements).
    space_symbol : str, optional
        Space group symbol.
    atom_count_range : list [min,max], optional
        Number of atoms range.
    predicted_formation_energy_range : list [min,max], optional
        Formation energy range (eV).
    band_gap_range : list [min,max], optional
        Band gap range (eV).
    n_results : int
        Max number of results to fetch (default: 10).
    output_formats : list of {"cif", "json"}
        Export formats. Default: "cif".

    📤 Returns:
    -----------------------------------
    FetchResult dict:
        - output_dir: Path to the output folder.
        - cleaned_structures: List of cleaned structures.
        - n_found: Number of results.
    """
    # === Step 1: Build filters ===
    filters = {}
    if elements:
        filters["elements"] = elements
    if spacegroup_number:
        sg_symbol = SPACEGROUP_UNICODE.get(int(spacegroup_number))
        if sg_symbol:
            filters["space_symbol"] = sg_symbol
        else:
            logging.warning(f"Unknown space group number: {spacegroup_number}")
    if atom_count_range:
        filters["atomCountRange"] = atom_count_range
    if predicted_formation_energy_range:
        filters["predicted_formation_energy_range"] = predicted_formation_energy_range
    if band_gap_range:
        filters["band_gap_range"] = band_gap_range

    # Default sort: lowest formation energy first (most stable materials)
    sort_filed_info = {"sort_filed": "crystal_ext.predicted_formation_energy", "sort_type": 1}

    # === Step 2: API call ===
    # user_info = get_user_info_by_ak()
    headers = {
        "X-User-Id": x_user_id,
        # "X-Org-Id": user_info["org_id"],
        "Content-Type": "application/json"
    }
    payload = {
        "material_type": "5",
        "keyword": formula or "",
        "positive_pole_key": filters,
        "match_mode": match_mode if (formula or elements) else 0,
        "sort_filed_info": sort_filed_info,
        "size": n_results,
        "page": 1,
    }

    try:
        url = f"{DB_CORE_HOST}/api/v1/crystal/list"
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
    except Exception as err:
        logging.error(f"Request failed: {err}")
        return {
            "output_dir": Path(),
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"Request failed: {err}",
        }

    items = data.get("data", {}).get("data", [])  # follow Bohrium return schema
    n_found = len(items)

    # === Step 3: Build output folder ===
    filter_str = f"{formula or ''}|n_results={n_results}|filters={json.dumps(filters, sort_keys=True)}"
    tag = tag_from_filters(
        formula=formula,
        elements=elements,
        spacegroup_number=spacegroup_number,
        atom_count_range=atom_count_range,
        predicted_formation_energy_range=predicted_formation_energy_range,
        band_gap_range=band_gap_range,
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha1(filter_str.encode("utf-8")).hexdigest()[:8]
    output_dir = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short_hash}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # === Step 4: Save ===
    cleaned = await to_thread.run_sync(lambda: save_structures_bohriumcrystal(
            items=items,
            output_dir=output_dir,
            output_formats=output_formats
        )
    )

    # === Step 5: Save manifest ===
    manifest = {
        "formula": formula,
        "filters": filters,
        "match_mode": match_mode,
        "n_found": n_found,
        "formats": output_formats,
        "output_dir": str(output_dir),
    }
    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return {
        "output_dir": output_dir,
        "n_found": n_found,
        "cleaned_structures": cleaned,
        "code": 0,
        "message": "Success",
    }



if __name__ == "__main__":
    result = asyncio.run(fetch_bohrium_crystals(
        formula="SiO2",
        # elements=["Na"],
        # match_mode=0,
        spacegroup_number=154,
        # atom_count_range=["1", "100"],
        # predicted_formation_energy_range=["-50", "50"],
        # band_gap_range=["1", "5"],
        n_results=3,
        # output_formats=["json", "cif"],
    ))
    print(result)