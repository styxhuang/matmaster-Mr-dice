import json
from pathlib import Path
from typing import List, Optional, Literal, TypedDict
from datetime import datetime, timezone

Format = Literal["cif", "json"]

# === Result return type ===
class FetchResult(TypedDict):
    output_dir: Path               # Folder where results are saved
    cleaned_structures: List[dict]  # List of cleaned structure dicts
    n_found: int                    # Number of structures found

def parse_iso8601_utc(dt_str: str) -> datetime:
    """
    Parse an ISO 8601 UTC datetime string like '2024-01-01T00:00:00Z'.
    """
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1]
    return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)

def crystal_structure_to_dict(cs, drop_sites: bool = False) -> dict:
    """
    Convert a CrystalStructure to a dict.

    Parameters
    ----------
    cs : CrystalStructure
    drop_sites : bool
        If True, exclude site information from structure.

    Returns
    -------
    dict
        Dictionary with selected structure fields.
    """
    struct_dict = cs.structure.as_dict()
    if drop_sites:
        struct_dict.pop("sites", None)

    return {
        "id": cs.id,
        "provider": cs.provider,
        "formula": cs.formula,
        "energy": cs.energy,
        "submission_time": cs.submission_time.isoformat(),
        "structure": struct_dict
    }


def tag_from_filters(
    formula: Optional[str] = None,
    min_energy: Optional[float] = None,
    max_energy: Optional[float] = None,
    min_submission_time: Optional[str] = None,
    max_submission_time: Optional[str] = None,
    max_len: int = 40
) -> str:
    parts = []
    if formula:
        parts.append(formula.replace(" ", ""))
    if min_energy is not None:
        parts.append(f"emin{min_energy:.2f}")
    if max_energy is not None:
        parts.append(f"emax{max_energy:.2f}")
    if min_submission_time is not None:
        dt = parse_iso8601_utc(min_submission_time)
        parts.append("tmin" + dt.strftime("%Y%m%d"))
    if max_submission_time is not None:
        dt = parse_iso8601_utc(max_submission_time)
        parts.append("tmax" + dt.strftime("%Y%m%d"))

    tag = "_".join(parts)
    return tag[:max_len] or "openlam"


def save_structures_openlam(
    items: List,
    output_dir: Path,
    output_formats: List[Format] = ["cif"]
) -> List[dict]:
    """
    Save OpenLAM crystal structures as full JSON and/or CIF files,
    and return a cleaned version of structure metadata.

    Parameters
    ----------
    items : list
        List of CrystalStructure objects.
    output_dir : Path
        Folder to save files into.
    output_formats : list of {"json", "cif"}
        Format(s) to export for each structure.

    Returns
    -------
    List of cleaned structure dicts (e.g., without site data).
    """
    from pymatgen.io.cif import CifWriter

    cleaned = []

    for i, cs in enumerate(items):
        name = f"{cs.provider or 'openlam'}_{cs.id}_{i}"

        # Save full JSON
        if "json" in output_formats:
            full_dict = crystal_structure_to_dict(cs, drop_sites=False)
            with open(output_dir / f"{name}.json", "w", encoding="utf-8") as f:
                json.dump(full_dict, f, indent=2, ensure_ascii=False)

        # Save CIF
        if "cif" in output_formats:
            CifWriter(cs.structure).write_file(output_dir / f"{name}.cif")

        # Collect cleaned version (for return)
        cleaned.append(crystal_structure_to_dict(cs, drop_sites=True))

    return cleaned