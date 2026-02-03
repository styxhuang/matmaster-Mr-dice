import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
import hashlib
import os
import sys
from anyio import to_thread

from dp.agent.server import CalculationMCPServer
from utils import *

# Add openlam path
openlam_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'openlam')
sys.path.insert(0, openlam_path)
from lam_optimize.db import CrystalStructure

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data_openlam")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETURNED_STRUCTS = 30

# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="OpenLAM MCP Server")
    parser.add_argument('--port', type=int, default=50002, help='Server port (default: 50002)')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    try:
        return parser.parse_args()
    except SystemExit:
        class Args:
            port = 50002
            host = '0.0.0.0'
            log_level = 'INFO'
        return Args()

# === OUTPUT TYPE ===
Format = Literal["cif", "json"]

class FetchResult(TypedDict):
    output_dir: Path             # folder where results are saved
    cleaned_structures: List[dict]  # list of cleaned structures
    n_found: int                    # number of structures found (0 if none)
    code: int
    message: str


# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("OpenLAMServer", port=args.port, host=args.host)

# === MCP TOOL ===
@mcp.tool()
async def fetch_openlam_structures(
    formula: Optional[str] = None,
    min_energy: Optional[float] = None,
    max_energy: Optional[float] = None,
    min_submission_time: Optional[str] = None,
    max_submission_time: Optional[str] = None,
    n_results: int = 10,
    output_formats: List[Format] = ["cif"]
) -> FetchResult:
    """
    📦 Fetch crystal structures from the OpenLAM database and save them to disk.

    🔍 What this tool does:
    -----------------------------------
    - Queries the OpenLAM materials database using optional filters.
    - Supports filtering by chemical formula, energy window, and submission time.
    - Saves structures in `.cif` and/or `.json` formats.
    - Automatically creates a tagged output folder and writes a manifest.

    🧩 Arguments:
    -----------------------------------
    formula : str, optional
        Chemical formula to filter structures (e.g., "Fe2O3").
    min_energy : float, optional
        Minimum energy value in eV.
    max_energy : float, optional
        Maximum energy value in eV.
    min_submission_time : str, optional
        Earliest submission time in ISO 8601 UTC format (e.g., "2024-01-01T00:00:00Z").
    max_submission_time : str, optional
        Latest submission time in ISO 8601 UTC format (e.g., "2025-01-01T00:00:00Z").
    n_results : int
        Max number of structures to fetch (default: 10).
    output_formats : list of {"cif", "json"}
        Which file formats to export for each structure. Default is .cif.

    📤 Returns:
    -----------------------------------
    FetchResult (dict) with:
        - output_dir: Path to the output folder.
        - cleaned_structures: List of cleaned structure dicts (metadata + lattice + species info).
        - n_found: Number of structures returned.

    📝 Notes:
    -----------------------------------
    - If no structures match, `output_dir` will be empty and `n_found=0`.
    - All outputs are stored under `materials_data/<tag>_<timestamp>_<hash>/`.

    Examples:
    -----------------------------------
    fetch_openlam_structures(
        formula="LiFePO4",
        min_energy=-50.0,
        max_energy=10.0,
        min_submission_time="2023-01-01T00:00:00Z",
        output_formats=["json", "cif"]
    )
    """
    # Normalize formula (convert subscript/superscript to normal numbers)
    if formula:
        formula = normalize_formula(formula)
    
    try:
        data = await to_thread.run_sync(lambda: CrystalStructure.query_by_offset(
            formula=formula,
            min_energy=min_energy,
            max_energy=max_energy,
            min_submission_time=parse_iso8601_utc(min_submission_time) if min_submission_time else None,
            max_submission_time=parse_iso8601_utc(max_submission_time) if max_submission_time else None,
            offset=0,
            limit=n_results,
        ))
    except Exception as e:
        logging.error(f"查询OpenLAM数据库时出错: {e}")
        return {
            "output_dir": Path(),
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"查询OpenLAM数据库时出错: {str(e)}",
        }

    items = data.get("items") or []

    # Build folder name from filters
    filter_str = f"{formula or ''}|emin={min_energy}|emax={max_energy}|tmin={min_submission_time}|tmax={max_submission_time}"
    tag = tag_from_filters(
        formula=formula,
        min_energy=min_energy,
        max_energy=max_energy,
        min_submission_time=min_submission_time,
        max_submission_time=max_submission_time
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha1(filter_str.encode("utf-8")).hexdigest()[:8]
    output_dir = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short_hash}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save structures
    try:
        cleaned = await to_thread.run_sync(lambda: save_structures_openlam(
            items=items,
            output_dir=output_dir,
            output_formats=output_formats
        ))
    except Exception as e:
        logging.error(f"保存结构时出错: {e}")
        return {
            "output_dir": output_dir,
            "n_found": 0,
            "cleaned_structures": [],
            "code": -1,
            "message": f"保存结构时出错: {str(e)}",
        }

    cleaned = cleaned[:MAX_RETURNED_STRUCTS]
    n_found = len(cleaned)

    # Save manifest
    manifest = {
        "formula": formula,
        "n_results": n_results,
        "filters": {
            "min_energy": min_energy,
            "max_energy": max_energy,
            "min_submission_time": min_submission_time,
            "max_submission_time": max_submission_time,
        },
        "n_found": n_found,
        "formats": output_formats,
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(manifest, indent=2))

    return {
        "output_dir": output_dir,
        "n_found": n_found,
        "cleaned_structures": cleaned,
        "code": -9999 if n_found == 0 else 0,
        "message": "Success",
    }

# === START SERVER ===
if __name__ == "__main__":
    logging.info("Starting OpenLAM MCP Server...")
    mcp.run(transport="sse")