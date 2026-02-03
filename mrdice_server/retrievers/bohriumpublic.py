import json
import logging
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

from .base import Retriever
from ..core.config import get_bohrium_output_dir
from ..models.schema import normalize_result, SearchResult


def _import_bohrium_utils():
    """
    Lazy import of Bohrium public utils to avoid import errors at module level.
    """
    try:
        # Add database directory to path if needed
        project_root = Path(__file__).parent.parent
        database_path = project_root / "database"
        if str(database_path) not in sys.path:
            sys.path.insert(0, str(database_path))

        from bohriumpublic_database.Bohriumpublic_Server.utils import (
            DB_CORE_HOST,
            SPACEGROUP_UNICODE,
            normalize_formula,
            save_structures_bohriumcrystal,
            x_user_id,
        )
        return {
            "DB_CORE_HOST": DB_CORE_HOST,
            "SPACEGROUP_UNICODE": SPACEGROUP_UNICODE,
            "normalize_formula": normalize_formula,
            "save_structures_bohriumcrystal": save_structures_bohriumcrystal,
            "x_user_id": x_user_id,
        }
    except ImportError as e:
        logging.error(f"Failed to import Bohrium utils: {e}")
        raise


class BohriumPublicRetriever:
    def __init__(self) -> None:
        self.base_output_dir = get_bohrium_output_dir()
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        self._utils = None

    def _get_utils(self):
        """Lazy load Bohrium utils."""
        if self._utils is None:
            self._utils = _import_bohrium_utils()
        return self._utils

    def fetch(self, filters: Dict[str, Any], n_results: int, output_format: str) -> List[SearchResult]:
        utils = self._get_utils()
        DB_CORE_HOST = utils["DB_CORE_HOST"]
        SPACEGROUP_UNICODE = utils["SPACEGROUP_UNICODE"]
        normalize_formula = utils["normalize_formula"]
        save_structures_bohriumcrystal = utils["save_structures_bohriumcrystal"]
        x_user_id = utils["x_user_id"]

        formula = filters.get("formula")
        elements = filters.get("elements")
        spacegroup_number = filters.get("space_group")
        band_gap = filters.get("band_gap") or {}
        energy = filters.get("energy") or {}

        if formula:
            formula = normalize_formula(formula)

        payload_filters: Dict[str, Any] = {}
        if elements:
            payload_filters["elements"] = elements
        if spacegroup_number:
            sg_symbol = SPACEGROUP_UNICODE.get(int(spacegroup_number))
            if sg_symbol:
                payload_filters["space_symbol"] = sg_symbol
            else:
                logging.warning(f"Unknown space group number: {spacegroup_number}")

        band_gap_range = None
        if band_gap.get("min") is not None or band_gap.get("max") is not None:
            band_gap_range = [
                str(band_gap.get("min") if band_gap.get("min") is not None else 0),
                str(band_gap.get("max") if band_gap.get("max") is not None else 100),
            ]
            payload_filters["band_gap_range"] = band_gap_range

        predicted_formation_energy_range = None
        if energy.get("min") is not None or energy.get("max") is not None:
            predicted_formation_energy_range = [
                str(energy.get("min") if energy.get("min") is not None else -100),
                str(energy.get("max") if energy.get("max") is not None else 100),
            ]
            payload_filters["predicted_formation_energy_range"] = predicted_formation_energy_range

        headers = {
            "X-User-Id": x_user_id,
            "Content-Type": "application/json",
        }
        payload = {
            "material_type": "5",
            "keyword": formula or "",
            "positive_pole_key": payload_filters,
            "match_mode": 1 if (formula or elements) else 0,
            "sort_filed_info": {"sort_filed": "crystal_ext.predicted_formation_energy", "sort_type": 1},
            "size": n_results,
            "page": 1,
        }

        try:
            url = f"{DB_CORE_HOST}/api/v1/crystal/list"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            data = response.json()
            items = data.get("data", {}).get("data", [])
        except Exception as exc:
            logging.error(f"Bohrium request failed: {exc}")
            return []

        filter_str = f"{formula or ''}|n_results={n_results}|filters={json.dumps(payload_filters, sort_keys=True)}"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_hash = hashlib.sha1(filter_str.encode("utf-8")).hexdigest()[:8]
        output_dir = self.base_output_dir / f"bohrium_{ts}_{short_hash}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_formats = [output_format]
        try:
            save_structures_bohriumcrystal(
                items=items,
                output_dir=output_dir,
                output_formats=output_formats,
            )
        except Exception as exc:
            logging.error(f"Bohrium save failed: {exc}")

        results: List[SearchResult] = []
        for i, struct in enumerate(items):
            struct_id = struct.get("id", f"idx{i}")
            name = f"bohriumcrystal_{struct_id}_{i}"
            structure_file = str(output_dir / f"{name}.{output_format}") if output_format else None
            elements_list = struct.get("elements") or []
            space_group = struct.get("space_symbol") or struct.get("space_group") or None
            n_atoms = struct.get("atomCount") or struct.get("atom_count")
            band_gap_val = struct.get("band_gap") or struct.get("crystal_ext", {}).get("band_gap")
            formation_energy = struct.get("predicted_formation_energy") or struct.get("crystal_ext", {}).get(
                "predicted_formation_energy"
            )
            results.append(
                normalize_result(
                    name=struct.get("name") or name,
                    structure_file=structure_file,
                    formula=struct.get("formula") or struct.get("reduced_formula"),
                    elements=elements_list,
                    space_group=space_group,
                    n_atoms=n_atoms,
                    band_gap=band_gap_val,
                    formation_energy=formation_energy,
                    source="bohriumpublic",
                    id=str(struct.get("id") or ""),
                )
            )

        return results
