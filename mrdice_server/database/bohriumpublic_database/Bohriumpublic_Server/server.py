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

MAX_RETURNED_STRUCTS = 30

# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="BohriumPublic MCP Server")
    parser.add_argument('--port', type=int, default=50003, help='Server port (default: 50003)')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    try:
        return parser.parse_args()
    except SystemExit:
        class Args:
            port = 50003
            host = '0.0.0.0'
            log_level = 'INFO'
        return Args()

# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("BohriumPublicServer", port=args.port, host=args.host)


# === MCP TOOL ===
@mcp.tool()
async def fetch_bohrium_crystals(
    formula: Optional[str] = None,
    elements: Optional[List[str]] = None,
    match_mode: int = 1,   # only effective for formula / elements
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
    spacegroup_number : int, optional
        Space group number.
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
        - code: 0 for success, -1 for error.
        - message: Error message if code is -1.
    """
    # === Step 0: Normalize formula (convert subscript/superscript to normal numbers) ===
    if formula:
        formula = normalize_formula(formula)
    
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
        # Auto-complete missing end: if one end is missing, fill with 0 (min) or 100 (max)
        processed_band_gap_range = band_gap_range.copy() if isinstance(band_gap_range, list) else []
        if len(processed_band_gap_range) == 1:
            # Only one value provided, assume it's min, set max to 100
            processed_band_gap_range.append("100")
        elif len(processed_band_gap_range) == 2:
            # Two values provided, check if either is missing
            if not processed_band_gap_range[0] or processed_band_gap_range[0] == "":
                processed_band_gap_range[0] = "0"
            if not processed_band_gap_range[1] or processed_band_gap_range[1] == "":
                processed_band_gap_range[1] = "100"
        filters["band_gap_range"] = processed_band_gap_range

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

    cleaned = cleaned[:MAX_RETURNED_STRUCTS]
    n_found = len(cleaned)

    # === Step 5: Save manifest ===
    manifest = {
        "formula": formula,
        "filters": filters,
        "match_mode": match_mode,
        "n_results": n_results,
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
        "code": -9999 if n_found == 0 else 0,
        "message": "Success",
    }


# === START SERVER ===
if __name__ == "__main__":
    logging.info("Starting Bohrium MCP Server...")
    mcp.run(transport="sse")