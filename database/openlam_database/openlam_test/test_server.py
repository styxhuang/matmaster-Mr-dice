import json
import sys
import os
import hashlib
import logging
from typing import Optional, List, Dict, TypedDict, Literal
from datetime import datetime
from pathlib import Path

# Add openlam path
openlam_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'openlam')
sys.path.insert(0, openlam_path)

from lam_optimize.db import CrystalStructure
from dotenv import load_dotenv
from utils import (
    crystal_structure_to_dict,
    tag_from_filters,
    save_structures_openlam,
    parse_iso8601_utc,
)

load_dotenv()

# === Output format type ===
Format = Literal["cif", "json"]

# === Result return type ===
class FetchResult(TypedDict):
    output_dir: Path
    cleaned_structures: List[dict]
    n_found: int

BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_openlam_structures(
    formula: Optional[str] = None,
    min_energy: Optional[float] = None,
    max_energy: Optional[float] = None,
    min_submission_time: Optional[str] = None,
    max_submission_time: Optional[str] = None,
    n_results: int = 10,
    output_formats: List[Format] = ["json", "cif"]
) -> FetchResult:
    """
    Fetch crystal structures from the OpenLAM database and save them to disk.

    Parameters
    ----------
    All time filters should be ISO 8601 UTC strings, e.g., "2024-01-01T00:00:00Z".

    Returns
    -------
    FetchResult
        Dictionary containing output folder path, number of structures, and cleaned data.
    """
    # === Step 1: Query ===
    data = CrystalStructure.query_by_offset(
        formula=formula,
        min_energy=min_energy,
        max_energy=max_energy,
        min_submission_time=parse_iso8601_utc(min_submission_time) if min_submission_time else None,
        max_submission_time=parse_iso8601_utc(max_submission_time) if max_submission_time else None,
        offset=0,
        limit=n_results,
    )

    items = data.get("items") or []
    n_found = len(items)

    # === Step 2: Build output folder ===
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

    # === Step 3: Save ===
    cleaned = save_structures_openlam(
        items=items,
        output_dir=output_dir,
        output_formats=output_formats
    )

    # === Step 4: Manifest ===
    manifest = {
        "formula": formula,
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

    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return {
        "output_dir": output_dir,
        "n_found": n_found,
        "cleaned_structures": cleaned,
    }


if __name__ == "__main__":
    result = fetch_openlam_structures(
        formula="Fe2O3",
        min_energy=-0.01,
        max_energy=0.01,
        min_submission_time="2024-09-01T00:00:00Z",
        max_submission_time="2025-01-01T00:00:00Z",
        n_results=5,
        output_formats=["json", "cif"]
    )

    print(result)