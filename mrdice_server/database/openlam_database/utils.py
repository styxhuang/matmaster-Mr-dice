import json
import os
from pathlib import Path
from typing import List, Optional, Literal
from datetime import datetime, timezone


def _mask_key(s: Optional[str]) -> str:
    """日志用：只显示是否非空及长度，不打印密钥内容。"""
    if s is None or s == "":
        return "None/empty"
    return f"<set,len={len(s)}>"


def set_bohrium_env(
    *,
    access_key: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """将 Bohrium 凭证写入环境变量，供 OpenLAM 等下游使用。MCP 与 CLI 共用。"""
    import logging
    _log = logging.getLogger("mrdice")
    _log.info(
        "[OpenLAM] set_bohrium_env 入参: access_key=%s, project_id=%s, user_id=%s",
        _mask_key(access_key), project_id or "None", user_id or "None",
    )
    if access_key is not None:
        os.environ["BOHRIUM_ACCESS_KEY"] = access_key
    if project_id is not None:
        os.environ["BOHRIUM_PROJECT_ID"] = str(project_id)
    if user_id is not None:
        os.environ["BOHRIUM_USER_ID"] = str(user_id)
    _log.info(
        "[OpenLAM] set_bohrium_env 后 env: BOHRIUM_ACCESS_KEY=%s, BOHRIUM_PROJECT_ID=%s, BOHRIUM_USER_ID=%s",
        _mask_key(os.environ.get("BOHRIUM_ACCESS_KEY")),
        os.environ.get("BOHRIUM_PROJECT_ID") or "None",
        os.environ.get("BOHRIUM_USER_ID") or "None",
    )


# === OUTPUT TYPE ===
Format = Literal["cif", "json"]

# Pre-built translation table for formula normalization (created once at module load)
_FORMULA_TRANSLATION_TABLE = str.maketrans({
    # Subscript numbers: ₀₁₂₃₄₅₆₇₈₉ (U+2080-U+2089)
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    # Superscript numbers: ⁰¹²³⁴⁵⁶⁷⁸⁹
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    # Full-width numbers: ０１２３４５６７８９ (U+FF10-U+FF19)
    '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
    '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
})

def normalize_formula(formula: Optional[str]) -> Optional[str]:
    """
    Convert subscript/superscript numbers in chemical formula to normal numbers.
    
    Uses efficient str.translate() for better performance. Supports:
    - Subscript numbers (₀₁₂₃...) → normal numbers (0123...)
    - Superscript numbers (⁰¹²³...) → normal numbers (0123...)
    - Full-width numbers (０１２３...) → normal numbers (0123...)
    
    Examples:
        SrTiO₃ → SrTiO3
        H₂O → H2O
        Fe₂O₃ → Fe2O3
    """
    if not formula:
        return formula
    return formula.translate(_FORMULA_TRANSLATION_TABLE)

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