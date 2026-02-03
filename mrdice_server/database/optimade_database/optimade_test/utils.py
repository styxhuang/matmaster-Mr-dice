import os
import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Iterable, Optional, Any, Tuple
from pymatgen.core import Composition, Structure
from pymatgen.symmetry.groups import SpaceGroup

import re

from urllib.parse import urlparse
import oss2
from dotenv import load_dotenv
from oss2.credentials import EnvironmentVariableCredentialsProvider

# === LOAD ENV ===
load_dotenv()


DEFAULT_PROVIDERS = {
    # "aflow",
    "alexandria",
    # "aiida",
    # "ccdc",
    # "ccpnc",
    "cmr",
    "cod",
    # "httk",
    # "jarvis",
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

DEFAULT_SPG_PROVIDERS = {
    "alexandria",
    "cod",
    "mpdd",
    "nmd",
    "odbx",
    "oqmd",
    "tcod",
}

DEFAULT_BG_PROVIDERS = {
    "alexandria",
    "odbx",
    "oqmd",
    "mcloudarchive",
    "twodmatpedia",
}

URLS_FROM_PROVIDERS = {
    "aflow": ["https://aflow.org/API/optimade/"],
    "alexandria": [
        "https://alexandria.icams.rub.de/pbe",
        "https://alexandria.icams.rub.de/pbesol"
    ],
    "cod": ["https://www.crystallography.net/cod/optimade"],
    "cmr": ["https://cmr-optimade.fysik.dtu.dk/"],
    "mcloud": [
        "https://optimade.materialscloud.io/main/mc3d-pbe-v1",
        "https://optimade.materialscloud.io/main/mc2d",
        "https://optimade.materialscloud.io/main/2dtopo",
        "https://optimade.materialscloud.io/main/tc-applicability",
        "https://optimade.materialscloud.io/main/pyrene-mofs",
        "https://optimade.materialscloud.io/main/curated-cofs",
        "https://optimade.materialscloud.io/main/stoceriaitf",
        "https://optimade.materialscloud.io/main/autowannier",
        "https://optimade.materialscloud.io/main/tin-antimony-sulfoiodide"
    ],
    "mcloudarchive": [
        "https://optimade.materialscloud.org/archive/zk-gc",
        "https://optimade.materialscloud.org/archive/c8-gy",
        "https://optimade.materialscloud.org/archive/5p-vq",
        "https://optimade.materialscloud.org/archive/vg-ya"
    ],
    "mp": ["https://optimade.materialsproject.org/"],
    "mpdd": ["http://mpddoptimade.phaseslab.org/"],
    "mpds": ["https://api.mpds.io/"],
    "mpod": ["http://mpod_optimade.cimav.edu.mx/"],
    "nmd": ["https://nomad-lab.eu/prod/rae/optimade/"],
    "odbx": [
        "https://optimade.odbx.science/",
        "https://optimade-misc.odbx.science/",
        "https://optimade-gnome.odbx.science/"
    ],
    "omdb": ["http://optimade.openmaterialsdb.se/"],
    "oqmd": ["https://oqmd.org/optimade/"],
    "jarvis": ["https://jarvis.nist.gov/optimade/jarvisdft"],
    "tcod": ["https://www.crystallography.net/tcod/optimade"],
    "twodmatpedia": ["http://optimade.2dmatpedia.org/"]
}

DROP_ATTRS = {
    "cartesian_site_positions",
    "species_at_sites",
    "species",
    "immutable_id",
    "_alexandria_charges",
    "_alexandria_magnetic_moments",
    "_alexandria_forces",
    "_alexandria_scan_forces",
    "_alexandria_scan_charges",
    "_alexandria_scan_magnetic_moments",
    "_nmd_dft_quantities",
    "_nmd_files",
    "_nmd_dft_geometries",
    "_mpdd_descriptors",
    "_mpdd_poscar",
}

# === UTILS ===
def hill_formula_filter(formula: str) -> str:
    hill_formula = Composition(formula).hill_formula.replace(' ', '')
    return f'chemical_formula_reduced="{hill_formula}"'

# regex for chemical_formula_reduced="..."/'...'
_CFR_EQ = re.compile(r'(?i)\bchemical_formula_reduced\b\s*=\s*([\'"])(.+?)\1')

def normalize_cfr_in_filter(filter_str: str) -> str:
    """Normalize all chemical_formula_reduced=... clauses (0, 1, many)."""
    if not filter_str:
        return filter_str

    def repl(m):
        raw = m.group(2)  # the formula
        return hill_formula_filter(raw)

    return _CFR_EQ.sub(repl, filter_str)


# def upload_file_to_oss(file_path: Path) -> str:
#     """
#     上传文件至 OSS, 返回公开访问链接
#     """
#     auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
#     endpoint = os.environ["OSS_ENDPOINT"]
#     bucket_name = os.environ["OSS_BUCKET_NAME"]
#     bucket = oss2.Bucket(auth, endpoint, bucket_name)

#     ext = file_path.suffix.lower().lstrip('.')
#     oss_filename = f"{ext}_{file_path.name}_{int(time.time())}.{ext}"
#     oss_path = f"retrosyn/{oss_filename}"

#     with open(file_path, "rb") as f:
#         bucket.put_object(oss_path, f)

#     region = endpoint.split('.')[0].replace("oss-", "")
#     return f"https://{bucket_name}.oss-{region}.aliyuncs.com/{oss_path}"



# === Saver ===
def _provider_name_from_url(url: str) -> str:
    """Turn provider URL into a filesystem-safe name."""
    parsed = urlparse(url)
    netloc = parsed.netloc.replace('.', '_')
    path = parsed.path.strip('/').replace('/', '_')
    name = f"{netloc}_{path}" if path else netloc
    return name.strip('_') or "provider"

def shorten_id(orig_id: str, head: int = 6, tail: int = 3, min_len: int = 12) -> str:
    """
    Shorten a long ID for display.

    Args:
        orig_id: the original string ID
        head: number of characters to keep at the start
        tail: number of characters to keep at the end
        min_len: minimum length before shortening is applied

    Returns:
        A shortened ID string like 'abcdef...xyz' if longer than min_len,
        otherwise the original ID unchanged.
    """
    if not orig_id:
        return orig_id
    if len(orig_id) > min_len:
        return f"{orig_id[:head]}...{orig_id[-tail:]}"
    return orig_id


def normalize_and_collect(results_list: List[Any]) -> Tuple[List[dict], Dict[str, Dict[str, int]]]:
    """
    Normalize results from asyncio.gather and collect stats.
    """
    norm_results: List[dict] = []
    stats: Dict[str, Dict[str, int]] = {}

    for r in results_list:
        if isinstance(r, Exception):
            logging.error(f"[spg] task returned exception: {r}")
            norm_results.append({"structures": {}})
            continue

        norm_results.append(r)

        if "structures" in r:
            for clause, url_dict in r["structures"].items():
                for url, payload in url_dict.items():
                    n_data = len(payload.get("data", []))
                    stats.setdefault(clause, {})[url] = n_data

    return norm_results, stats


def distribute_quota_fair(stats: Dict[str, Dict[str, int]], n_results: int) -> Dict[str, Dict[str, int]]:
    """
    Strict fairness:
      1) Equalize across *active* clauses (providers) first (off by at most 1), respecting clause capacities.
      2) Inside each clause, distribute its clause-quota fairly across URLs (equal + water-fill), respecting URL caps.
      3) If some clauses can't absorb their fair share, *water-fill across clauses* to equalize totals,
         and for each unit given to a clause, assign it round-robin across that clause's residual URLs.
    - Preserves insertion order of `stats` (providers, then URLs).
    """
    if not stats or n_results <= 0:
        return {}

    clauses = list(stats.keys())
    # Clause capacities (sum of URL caps)
    clause_caps = {c: sum(stats[c].values()) for c in clauses}
    active_clauses = [c for c in clauses if clause_caps[c] > 0]
    plan: Dict[str, Dict[str, int]] = {c: {u: 0 for u in stats[c].keys()} for c in clauses}

    if not active_clauses:
        return plan

    # --- Step 1: initial equal targets across active clauses (base + remainder), capped by clause capacity
    n_active = len(active_clauses)
    base_clause = n_results // n_active
    rem_clause  = n_results %  n_active

    clause_targets = {c: 0 for c in clauses}
    for idx, c in enumerate(active_clauses):
        want = base_clause + (1 if idx < rem_clause else 0)
        clause_targets[c] = min(clause_caps[c], want)

    # --- Step 2: inside each clause, allocate its target across URLs fairly (equal + intra-clause water-fill)
    totals = {c: 0 for c in clauses}  # current assigned per clause
    for c in active_clauses:
        quota_c = clause_targets[c]
        if quota_c <= 0:
            continue

        urls = list(stats[c].keys())
        caps = [stats[c][u] for u in urls]
        n_urls = len(urls)

        # equal split
        base_url = quota_c // n_urls
        rem_url  = quota_c %  n_urls

        assigned = [0] * n_urls
        for ui, u in enumerate(urls):
            want = base_url + (1 if ui < rem_url else 0)
            give = min(want, caps[ui])
            assigned[ui] = give

        # intra-clause water-fill to reach quota_c if some URLs had headroom
        assigned_sum = sum(assigned)
        left = max(0, quota_c - assigned_sum)
        if left > 0:
            residuals = [caps[i] - assigned[i] for i in range(n_urls)]
            ui = 0
            while left > 0 and any(r > 0 for r in residuals):
                if residuals[ui] > 0:
                    assigned[ui] += 1
                    residuals[ui] -= 1
                    left -= 1
                ui = (ui + 1) % n_urls

        # write back
        for ui, u in enumerate(urls):
            plan[c][u] = assigned[ui]
        totals[c] = sum(assigned)

    # --- Step 3: clause-level water-filling (equalize across providers), then per-clause URL RR
    remaining = n_results - sum(totals.values())
    if remaining <= 0:
        return plan

    # per-clause URL residual lists + round-robin pointer
    residual_urls: Dict[str, List[List]] = {}
    next_url_idx: Dict[str, int] = {}
    for c in active_clauses:
        lst = []
        for u in stats[c].keys():
            res = stats[c][u] - plan[c][u]
            if res > 0:
                lst.append([u, res])  # [url, residual]
        if lst:
            residual_urls[c] = lst
            next_url_idx[c] = 0

    # helper: one unit to clause c → assign to next residual URL in that clause (RR)
    def give_one_to_clause(c: str) -> bool:
        urls = residual_urls.get(c)
        if not urls:
            return False
        idx = next_url_idx[c] % len(urls)
        u, r = urls[idx]
        plan[c][u] += 1
        totals[c] += 1
        r -= 1
        if r == 0:
            urls.pop(idx)
            next_url_idx[c] = 0 if not urls else (idx % len(urls))
            if not urls:
                residual_urls.pop(c, None)
        else:
            urls[idx][1] = r
            next_url_idx[c] = (idx + 1) % len(urls)
        return True

    # clause-level water-filling: always raise clauses with the current minimum total first
    while remaining > 0 and residual_urls:
        # among clauses that still have residual URLs, find current minimal total
        candidates = [c for c in active_clauses if c in residual_urls]
        if not candidates:
            break
        min_total = min(totals[c] for c in candidates)

        progressed = False
        for c in active_clauses:  # preserve insertion order
            if remaining == 0:
                break
            if c not in residual_urls:
                continue
            if totals[c] == min_total:
                if give_one_to_clause(c):
                    remaining -= 1
                    progressed = True

        if not progressed:
            # no clause at min_total could accept more (capacity bound) → stop
            break

    return plan


def save_structures(results: Dict, output_folder: Path, as_cif: bool, plan: Dict[str, Dict[str, int]]):
    """
    Walk OPTIMADE aggregated results and write per-provider files using per-URL quotas from `plan`.
    Returns files list, warnings list, providers_seen list, cleaned_structures list.
    """
    output_folder.mkdir(parents=True, exist_ok=True)
    files: List[str] = []
    warnings: List[str] = []
    providers_seen: List[str] = []
    cleaned_structures: List[dict] = []

    seen_ids: set[str] = set()

    structures_by_filter = results.get("structures", {})
    if not isinstance(structures_by_filter, dict):
        return files, warnings, providers_seen, cleaned_structures

    # iterate ALL clauses
    for clause, structures_by_url in structures_by_filter.items():
        if not isinstance(structures_by_url, dict):
            continue

        for provider_url, content in structures_by_url.items():
            # per-URL quota from plan
            quota = int(plan.get(clause, {}).get(provider_url, 0))
            if quota <= 0:
                continue

            provider_name = _provider_name_from_url(provider_url)
            providers_seen.append(provider_name)

            data_list = (content or {}).get("data", []) or []
            logging.info(f"[save] {provider_name}: {len(data_list)} candidates, quota={quota}")

            saved = 0
            for structure_data in data_list:
                if saved >= quota:
                    break

                orig_id = str(structure_data.get("id", ""))
                if not orig_id:
                    logging.warning(f"[save] missing id for {provider_name}; skipping")
                    continue
                if orig_id in seen_ids:
                    logging.debug(f"[save] duplicate skipped: {orig_id}")
                    continue

                # ---------- file write ----------
                suffix = "cif" if as_cif else "json"
                filename = f"{provider_name}_{orig_id}_{saved}.{suffix}"
                file_path = output_folder / filename

                try:
                    if as_cif:
                        cif_content = Structure(
                            lattice=structure_data['attributes']['lattice_vectors'],
                            species=structure_data['attributes']['species_at_sites'],
                            coords=structure_data['attributes']['cartesian_site_positions'],
                            coords_are_cartesian=True,
                        ).to(fmt='cif')
                        if not cif_content or not cif_content.strip():
                            raise ValueError("CIF content is empty")
                        file_path.write_text(cif_content)
                    else:
                        file_path.write_text(json.dumps(structure_data, indent=2, ensure_ascii=False))

                    logging.debug(f"[save] wrote {file_path}")
                    files.append(str(file_path))
                except Exception as e:
                    msg = f"Failed to save structure from {provider_name} #{orig_id}: {e}"
                    logging.warning(msg)
                    warnings.append(msg)
                    # don't mark seen; let another url try this id
                    continue

                # ---------- cleaned copy ----------
                try:
                    sd = dict(structure_data)
                    attrs = dict(sd.get("attributes", {}) or {})
                    for k in DROP_ATTRS:
                        attrs.pop(k, None)
                    sd["attributes"] = attrs
                    sd["provider_url"] = provider_url   # keep as you had it
                    cleaned_structures.append(sd)
                except Exception as e:
                    logging.warning(f"[save] clean-copy failed for {provider_name} #{orig_id}: {e}")

                # only after successful write:
                seen_ids.add(orig_id)
                saved += 1

            if saved < quota:
                warnings.append(
                    f"[save] underfilled quota for {provider_name} @ {provider_url}: wanted {quota}, saved {saved}"
                )

    # de-dup providers_seen preserving order
    providers_seen = list(dict.fromkeys(providers_seen))
    return files, warnings, providers_seen, cleaned_structures


def filter_to_tag(filter_str: str, max_len: int = 30) -> str:
    """
    Convert an OPTIMADE filter string into a short, filesystem-safe tag.

    Parameters
    ----------
    filter_str : str
        The original OPTIMADE filter string.
    max_len : int, optional
        Maximum length of the resulting tag (default: 30).

    Returns
    -------
    str
        A short, sanitized tag derived from the filter.
    """
    # Remove surrounding spaces and quotes
    tag = filter_str.strip().replace('"', '').replace("'", "")

    # Replace spaces, commas, and equals with underscores/dashes
    tag = tag.replace(" ", "_").replace(",", "-").replace("=", "")

    # Keep only safe characters: alphanumeric, underscore, dash
    tag = "".join(c for c in tag if c.isalnum() or c in "_-")

    # Limit length
    if len(tag) > max_len:
        tag = tag[:max_len]

    # Fallback if everything gets stripped
    return tag or "filter"



def _hm_symbol_from_number(spg_number: int) -> Optional[str]:
    """Return the short Hermann–Mauguin symbol (e.g. 'Im-3m') for a space-group number."""
    try:
        return SpaceGroup.from_int_number(spg_number).symbol
    except Exception as e:
        logging.warning(f"[spg] cannot map number {spg_number} to H–M symbol: {e}")
        return None

def _to_tcod_format(hm: str) -> str:
    """
    Convert a short Hermann–Mauguin symbol to TCOD spacing.
    Examples:
        'Pm-3m'   -> 'P m -3 m'
        'P4/mmm'  -> 'P 4/m m m'
        'Fd-3m'   -> 'F d -3 m'
    """
    s = hm.strip()
    # 1) Expand groups after '/' → '/m m m', '/mm' → '/m m', '/mc' → '/m c', etc.
    s = re.sub(r'/([A-Za-z]+)', lambda m: '/' + ' '.join(m.group(1)), s)
    # 2) Put spaces between ANY two consecutive letters (F d, P m, …)
    s = re.sub(r'(?<=[A-Za-z])(?=[A-Za-z])', ' ', s)
    # 3) Put spaces between letter↔digit transitions (P4 → P 4, 4m → 4 m)
    s = re.sub(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])', ' ', s)
    # 4) Put a space only *before* the minus (attach '-' to the number): 'm-3' -> 'm -3'
    s = re.sub(r'\s*-\s*(?=\d)', ' -', s)
    # 5) Collapse multiple spaces
    return ' '.join(s.split())

def get_spg_filter_map(spg_number: int, providers: Iterable[str]) -> Dict[str, str]:
    """
    Map provider name → space-group filter clause for that provider.
    Handles alexandria, nmd, mpdd, odbx, oqmd, tcod, cod.
    """
    hm = _hm_symbol_from_number(spg_number)

    name_map = {
        "alexandria": lambda: f"_alexandria_space_group={spg_number}",
        "nmd":        lambda: f"_nmd_dft_spacegroup={spg_number}",
        "mpdd":       lambda: f"_mpdd_spacegroupn={spg_number}",
        "odbx":       lambda: f"_gnome_space_group_it_number={spg_number}",
        "oqmd":       lambda: f'_oqmd_spacegroup="{hm}"' if hm else "",
        "tcod":       lambda: f'_tcod_sg="{_to_tcod_format(hm)}"' if hm else "",
        "cod":        lambda: f'_cod_sg="{_to_tcod_format(hm)}"' if hm else "",
    }

    out: Dict[str, str] = {}
    for p in providers:
        if p in name_map:
            clause = name_map[p]()
            if clause:
                out[p] = clause
    return out


def _range_clause(prop: str, min_bg: Optional[float], max_bg: Optional[float]) -> str:
    """Return OPTIMADE range clause like: prop>=a AND prop<=b (handles open ends)."""
    parts = []
    if min_bg is not None:
        parts.append(f"{prop}>={min_bg}")
    if max_bg is not None:
        parts.append(f"{prop}<={max_bg}")
    return " AND ".join(parts) if parts else ""  # empty means 'no constraint'

def get_bandgap_filter_map(
    min_bg: Optional[float],
    max_bg: Optional[float],
    providers: Optional[Iterable[str]] = None,
) -> Dict[str, str]:
    """
    Map provider name → band-gap clause using provider-specific property names.
    Providers without a known property are omitted.
    If providers is None, uses DEFAULT_BG_PROVIDERS.
    """
    providers = set(providers) if providers else DEFAULT_BG_PROVIDERS

    name_map = {
        "alexandria": "_alexandria_band_gap",
        "odbx": "_gnome_bandgap",             
        "oqmd": "_oqmd_band_gap",
        "mcloudarchive": "_mcloudarchive_band_gap",
        "twodmatpedia": "_twodmatpedia_band_gap",
    }

    out: Dict[str, str] = {}
    for p in providers:
        prop = name_map.get(p)
        if not prop:
            continue
        clause = _range_clause(prop, min_bg, max_bg)
        if clause:
            out[p] = clause
    return out

def build_provider_filters(base: Optional[str], provider_map: Dict[str, str]) -> Dict[str, str]:
    """
    Combine a base OPTIMADE filter with per-provider clauses.

    Parameters
    ----------
    base : str, optional
        Common OPTIMADE filter applied to all providers (can be empty/None).
    provider_map : dict
        {provider: specific_clause} mapping for each provider.

    Returns
    -------
    dict
        {provider: combined_clause}
    """
    b = (base or "").strip()
    return {
        p: f"({b}) AND ({c.strip()})" if b and c.strip() else (b or c.strip())
        for p, c in provider_map.items()
        if c and c.strip()  # skip empty clauses
    }


def get_base_urls() -> List[str]:

    try:
        from optimade.utils import get_all_databases

        base_urls = list(get_all_databases())
        return base_urls

    except ImportError:
        print("Warning: optimade.utils not available")
        return []
    except Exception as e:
        print(f"Error getting base URLs: {e}")
        return []


if __name__ == "__main__":
    urls = get_base_urls()
    print(urls)
    print(len(urls))



    # # 0 occurrence
    # f0 = 'elements HAS ANY "Si","O"'
    # print(normalize_cfr_in_filter(f0))
    # # -> elements HAS ANY "Si","O"

    # # 1 occurrence
    # f1 = 'chemical_formula_reduced="SiO2"'
    # print(normalize_cfr_in_filter(f1))
    # # -> chemical_formula_reduced="O2Si"

    # # 2 occurrences
    # f2 = '(chemical_formula_reduced="SiO2" OR chemical_formula_reduced="Al2O3")'
    # print(normalize_cfr_in_filter(f2))
    # # -> (chemical_formula_reduced="O2Si" OR chemical_formula_reduced="Al2O3")

    # # 4 occurrences
    # f4 = ('(chemical_formula_reduced="SiO2" OR chemical_formula_reduced="Al2O3") '
    #     'AND (chemical_formula_reduced="MgO" OR chemical_formula_reduced="NaCl")')
    # print(normalize_cfr_in_filter(f4))
    # # -> (chemical_formula_reduced="O2Si" OR chemical_formula_reduced="Al2O3") 
    # #    AND (chemical_formula_reduced="MgO" OR chemical_formula_reduced="ClNa")