import json
from pathlib import Path
from typing import List, Optional, Literal, TypedDict
from datetime import datetime, timezone

import requests
import logging
import json
import os
from dotenv import load_dotenv
import requests


load_dotenv()

global DB_CORE_HOST
global BOHRIUM_CORE_HOST
# DB_CORE_HOST="https://db-core.test.dp.tech"
# BOHRIUM_CORE_HOST="https://bohrium-core.test.dp.tech"
DB_CORE_HOST="https://db-core.dp.tech"
BOHRIUM_CORE_HOST="https://bohrium-core.dp.tech"


# def get_user_info_by_ak() -> dict:
#     """
#     根据ak获取用户信息
#     """
#     ak = os.getenv("BOHRIUM_ACCESS_KEY", "a43c365d70964ff6b22710da97b46254")
#     if not ak:
#         raise ValueError("BOHRIUM_ACCESS_KEY environment variable is not set")
    
#     url = f"{BOHRIUM_CORE_HOST}/api/v1/ak/get_user?accessKey={ak}"
    
#     try:
#         response = requests.get(url)
#         response.raise_for_status()
#         data = response.json()
        
#         if data.get("code") == 0 and "data" in data:
#             return {
#                 "user_id": str(data["data"]["userId"]),
#                 "org_id": str(data["data"]["orgId"])
#             }
#         else:
#             raise Exception(f"API returned error: {data}")
            
#     except Exception as e:
#         raise Exception(f"Failed to get user info: {str(e)}")
x_user_id = '117756'

CRYSTAL_DROP_ATTRS = {
    "cif_file",
    "come_from",
    "material_id",
}

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


def tag_from_filters(
    formula: Optional[str] = None,
    elements: Optional[List[str]] = None,
    spacegroup_number: Optional[int] = None,
    atom_count_range: Optional[List[str]] = None,
    predicted_formation_energy_range: Optional[List[str]] = None,
    band_gap_range: Optional[List[str]] = None,
    max_len: int = 60
) -> str:
    """
    Build a short tag string from Bohrium query filters.

    This tag is used to create unique output directories.

    Parameters
    ----------
    formula : str, optional
        Chemical formula keyword.
    elements : list of str, optional
        Required elements.
    spacegroup_number : int, optional
        Space group number (1-230).
    atom_count_range : [min,max], optional
        Atom count range.
    predicted_formation_energy_range : [min,max], optional
        Formation energy range (eV).
    band_gap_range : [min,max], optional
        Band gap range (eV).
    max_len : int
        Maximum length of the tag string.

    Returns
    -------
    str
        Shortened tag string (safe for filenames).
    """
    parts = []

    if formula:
        parts.append(formula.replace(" ", ""))
    if elements:
        parts.append("El" + "".join(sorted(elements)))
    if spacegroup_number:
        parts.append(f"Sg{spacegroup_number}")
    if atom_count_range:
        parts.append("Nat" + "-".join(atom_count_range))
    if predicted_formation_energy_range:
        parts.append("E" + "-".join(predicted_formation_energy_range))
    if band_gap_range:
        parts.append("Bg" + "-".join(band_gap_range))

    tag = "_".join(parts)
    return tag[:max_len] or "bohriumcrystal"


def save_structures_bohriumcrystal(
    items: List[dict],
    output_dir: Path,
    output_formats: List[Literal["json", "cif"]] = ["cif"]
) -> List[dict]:
    """
    Save Bohrium crystal structures as JSON and/or CIF files.

    Parameters
    ----------
    items : list of dict
        Structures returned from Bohrium API (already JSON dicts).
    output_dir : Path
        Directory to save files into.
    output_formats : list of {"json", "cif"}
        Which formats to save. Default is ["json"].

    Returns
    -------
    cleaned : list of dict
        Metadata-only version of the structures (same as items).
    """

    cleaned = []

    for i, struct in enumerate(items):
        struct_id = struct.get("id", f"idx{i}")
        name = f"bohriumcrystal_{struct_id}_{i}"

        # Save JSON
        if "json" in output_formats:
            with open(output_dir / f"{name}.json", "w", encoding="utf-8") as f:
                json.dump(struct, f, indent=2, ensure_ascii=False)

        # Save CIF (download from URL)
        if "cif" in output_formats:
            cif_url = struct.get("cif_file")
            if not cif_url:
                logging.warning(f"No CIF URL for {struct_id}")
            else:
                try:
                    r = requests.get(cif_url, timeout=30)
                    r.raise_for_status()
                    with open(output_dir / f"{name}.cif", "wb") as f:
                        f.write(r.content)
                    logging.info(f"Saved CIF for {struct_id} -> {name}.cif")
                except Exception as e:
                    logging.error(f"Failed to download CIF for {struct_id}: {e}")

        # Make a cleaned copy (remove bulky parts like CIF URL or details)
        cleaned_struct = dict(struct)
        for key in CRYSTAL_DROP_ATTRS:
            cleaned_struct.pop(key, None)
        cleaned.append(cleaned_struct)

    return cleaned


SPACEGROUP_UNICODE = {
    1: "P1",
    2: "P1̅",
    3: "P2",
    4: "P2₁",
    5: "C2",
    6: "Pm",
    7: "Pc",
    8: "Cm",
    9: "Cc",
    10: "P2/m",
    11: "P2₁/m",
    12: "C2/m",
    13: "P2/c",
    14: "P2₁/c",
    15: "C2/c",
    16: "P222",
    17: "P222₁",
    18: "P2₁2₁2",
    19: "P2₁2₁2₁",
    20: "C222₁",
    21: "C222",
    22: "F222",
    23: "I222",
    24: "I2₁2₁2₁",
    25: "Pmm2",
    26: "Pmc2₁",
    27: "Pcc2",
    28: "Pma2",
    29: "Pca2₁",
    30: "Pnc2",
    31: "Pmn2₁",
    32: "Pba2",
    33: "Pna2₁",
    34: "Pnn2",
    35: "Cmm2",
    36: "Cmc2₁",
    37: "Ccc2",
    38: "Amm2",
    39: "Aem2",
    40: "Ama2",
    41: "Aea2",
    42: "Fmm2",
    43: "Fdd2",
    44: "Imm2",
    45: "Iba2",
    46: "Ima2",
    47: "Pmmm",
    48: "Pnnn",
    49: "Pccm",
    50: "Pban",
    51: "Pmma",
    52: "Pnna",
    53: "Pmna",
    54: "Pcca",
    55: "Pbam",
    56: "Pccn",
    57: "Pbcm",
    58: "Pnnm",
    59: "Pmmn",
    60: "Pbcn",
    61: "Pbca",
    62: "Pnma",
    63: "Cmcm",
    64: "Cmce",
    65: "Cmmm",
    66: "Cccm",
    67: "Cmme",
    68: "Ccce",
    69: "Fmmm",
    70: "Fddd",
    71: "Immm",
    72: "Ibam",
    73: "Ibca",
    74: "Imma",
    75: "P4",
    76: "P4₁",
    77: "P4₂",
    78: "P4₃",
    79: "I4",
    80: "I4₁",
    81: "P̅4",
    82: "I̅4",
    83: "P4/m",
    84: "P4₂/m",
    85: "P4/n",
    86: "P4₂/n",
    87: "I4/m",
    88: "I4₁/a",
    89: "P422",
    90: "P42₁2",
    91: "P4₁2₂",
    92: "P4₁2₁2",
    93: "P4₂2₂",
    94: "P4₂2₁2",
    95: "P4₃2₂",
    96: "P4₃2₁2",
    97: "I422",
    98: "I4₁22",
    99: "P4mm",
    100: "P4bm",
    101: "P4₂cm",
    102: "P4₂nm",
    103: "P4cc",
    104: "P4nc",
    105: "P4₂mc",
    106: "P4₂bc",
    107: "I4mm",
    108: "I4cm",
    109: "I4₁md",
    110: "I4₁cd",
    111: "P̅42m",
    112: "P̅42c",
    113: "P̅421m",
    114: "P̅421c",
    115: "P̅4m2",
    116: "P̅4c2",
    117: "P̅4b2",
    118: "P̅4n2",
    119: "I̅4m2",
    120: "I̅4c2",
    121: "I̅42m",
    122: "I̅42d",
    123: "P4/mmm",
    124: "P4/mcc",
    125: "P4/nbm",
    126: "P4/nnc",
    127: "P4/mbm",
    128: "P4/mnc",
    129: "P4/nmm",
    130: "P4/ncc",
    131: "P4₂/mmc",
    132: "P4₂/mcm",
    133: "P4₂/nbc",
    134: "P4₂/nnm",
    135: "P4₂/mbc",
    136: "P4₂/mnm",
    137: "P4₂/nmc",
    138: "P4₂/ncm",
    139: "I4/mmm",
    140: "I4/mcm",
    141: "I4₁/amd",
    142: "I4₁/acd",
    143: "P3",
    144: "P3₁",
    145: "P3₂",
    146: "R3",
    147: "P̅3",
    148: "R̅3",
    149: "P312",
    150: "P321",
    151: "P3₁12",
    152: "P3₁21",
    153: "P3₂12",
    154: "P3₂21",
    155: "R32",
    156: "P3m1",
    157: "P31m",
    158: "P3c1",
    159: "P31c",
    160: "R3m",
    161: "R3c",
    162: "P̅31m",
    163: "P̅31c",
    164: "P̅3m1",
    165: "P̅3c1",
    166: "R̅3m",
    167: "R̅3c",
    168: "P6",
    169: "P6₁",
    170: "P6₅",
    171: "P6₂",
    172: "P6₄",
    173: "P6₃",
    174: "P̅6",
    175: "P6/m",
    176: "P6₃/m",
    177: "P622",
    178: "P6₁22",
    179: "P6₅22",
    180: "P6₂22",
    181: "P6₄22",
    182: "P6₃22",
    183: "P6mm",
    184: "P6cc",
    185: "P6₃cm",
    186: "P6₃mc",
    187: "P̅6m2",
    188: "P̅6c2",
    189: "P̅62m",
    190: "P̅62c",
    191: "P6/mmm",
    192: "P6/mcc",
    193: "P6₃/mcm",
    194: "P6₃/mmc",
    195: "P23",
    196: "F23",
    197: "I23",
    198: "P2₁3",
    199: "I2₁3",
    200: "Pm3̅",
    201: "Pn3̅",
    202: "Fm3̅",
    203: "Fd3̅",
    204: "Im3̅",
    205: "Pa3̅",
    206: "Ia3̅",
    207: "P432",
    208: "P4₂32",
    209: "F432",
    210: "F4₁32",
    211: "I432",
    212: "P4₃32",
    213: "P4₁32",
    214: "I4₁32",
    215: "P̅43m",
    216: "F̅43m",
    217: "I̅43m",
    218: "P̅43n",
    219: "F̅43c",
    220: "I̅43d",
    221: "Pm3̅m",
    222: "Pn3̅n",
    223: "Pm3̅n",
    224: "Pn3̅m",
    225: "Fm3̅m",
    226: "Fm3̅c",
    227: "Fd3̅m",
    228: "Fd3̅c",
    229: "Im3̅m",
    230: "Ia3̅d",
}
