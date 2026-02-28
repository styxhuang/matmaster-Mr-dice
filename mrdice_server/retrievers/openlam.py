import json
import logging
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseRetriever
from ..core.config import get_data_dir
from ..models.schema import SearchResult
from ..database.openlam_database.utils import set_bohrium_env


def _import_openlam_utils():
    """
    Lazy import of OpenLAM utils to avoid import errors at module level.
    """
    try:
        project_root = Path(__file__).parent.parent
        database_path = project_root / "database"
        if str(database_path) not in sys.path:
            sys.path.insert(0, str(database_path))

        from openlam_database.utils import (
            normalize_formula,
            save_structures_openlam,
            tag_from_filters,
            parse_iso8601_utc,
        )
        return {
            "normalize_formula": normalize_formula,
            "save_structures_openlam": save_structures_openlam,
            "tag_from_filters": tag_from_filters,
            "parse_iso8601_utc": parse_iso8601_utc,
        }
    except ImportError as e:
        logging.error(f"Failed to import OpenLAM utils: {e}")
        raise


def _import_crystal_structure():
    """
    Lazy import of CrystalStructure class from OpenLAM.
    """
    try:
        project_root = Path(__file__).parent.parent
        openlam_root = project_root / "database" / "openlam_database" / "openlam"
        if str(openlam_root) not in sys.path:
            sys.path.insert(0, str(openlam_root))

        from lam_optimize.db import CrystalStructure
        return CrystalStructure
    except ImportError as e:
        logging.error(f"Failed to import CrystalStructure: {e}")
        raise


class OpenlamRetriever(BaseRetriever):
    def __init__(self) -> None:
        self.data_dir = get_data_dir()
        self._utils = None
        self._CrystalStructure = None

    def _get_utils(self):
        """Lazy load OpenLAM utils."""
        if self._utils is None:
            self._utils = _import_openlam_utils()
        return self._utils

    def _get_crystal_structure(self):
        """Lazy load CrystalStructure class."""
        if self._CrystalStructure is None:
            self._CrystalStructure = _import_crystal_structure()
        return self._CrystalStructure

    def fetch(self, filters: Dict[str, Any], n_results: int, output_format: str) -> List[SearchResult]:
        # 使用与 CLI 一致的凭证注入：从环境变量写入，供 OpenLAM API 使用
        set_bohrium_env(
            access_key=os.getenv("BOHRIUM_ACCESS_KEY"),
            project_id=os.getenv("BOHRIUM_PROJECT_ID"),
            user_id=os.getenv("BOHRIUM_USER_ID"),
        )
        utils = self._get_utils()
        normalize_formula = utils["normalize_formula"]
        save_structures_openlam = utils["save_structures_openlam"]
        tag_from_filters = utils["tag_from_filters"]
        parse_iso8601_utc = utils["parse_iso8601_utc"]
        
        CrystalStructure = self._get_crystal_structure()

        # Extract filters
        formula = filters.get("formula")
        if formula:
            formula = normalize_formula(formula)

        energy = filters.get("energy") or {}
        min_energy = energy.get("min")
        max_energy = energy.get("max")

        time_range = filters.get("time_range") or {}
        min_submission_time_str = time_range.get("start")
        max_submission_time_str = time_range.get("end")
        
        min_submission_time = None
        max_submission_time = None
        if min_submission_time_str:
            try:
                min_submission_time = parse_iso8601_utc(min_submission_time_str)
            except Exception as e:
                logging.warning(f"Failed to parse min_submission_time: {e}")
        if max_submission_time_str:
            try:
                max_submission_time = parse_iso8601_utc(max_submission_time_str)
            except Exception as e:
                logging.warning(f"Failed to parse max_submission_time: {e}")

        # Query OpenLAM database
        try:
            data = CrystalStructure.query_by_offset(
                formula=formula,
                min_energy=min_energy,
                max_energy=max_energy,
                min_submission_time=min_submission_time,
                max_submission_time=max_submission_time,
                offset=0,
                limit=n_results,
            )
            structures = data.get("items", [])
        except Exception as exc:
            logging.error(f"OpenLAM query failed: {exc}")
            return []

        if not structures:
            return []

        # Save structures
        filter_str = f"{formula or ''}|energy={min_energy}-{max_energy}|time={min_submission_time_str}-{max_submission_time_str}|n_results={n_results}"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_hash = hashlib.sha1(filter_str.encode("utf-8")).hexdigest()[:8]
        output_dir = self.data_dir / "mrdice_server" / "database" / "openlam_database" / "materials_data_openlam" / f"emin{min_energy or 0.0:.2f}_{ts}_{short_hash}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_formats = [output_format] if output_format else ["cif"]
        try:
            cleaned_structures = save_structures_openlam(
                items=structures,
                output_dir=output_dir,
                output_formats=output_formats,
            )
        except Exception as exc:
            logging.error(f"OpenLAM save failed: {exc}")
            cleaned_structures = []

        # Convert to SearchResult
        results: List[SearchResult] = []
        for i, cs in enumerate(structures):
            name = f"openlam_{cs.id}_{i}"
            
            # Determine structure file path
            structure_file = self.build_structure_file_path(output_dir, name, output_format, check_exists=True)

            results.append(
                self.create_crystal_search_result(
                    name=name,
                    structure_file=structure_file,
                    formula=cs.formula,
                    space_group=None,  # OpenLAM doesn't provide space group
                    n_atoms=None,
                    band_gap=None,
                    formation_energy=cs.energy,
                    source="openlam",
                    id=str(cs.id),
                )
            )

        return results

