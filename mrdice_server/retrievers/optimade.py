import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseRetriever
from ..core.config import get_data_dir, get_optimade_timeouts
from ..core.error import ErrorType, MrDiceError
from ..models.schema import SearchResult


def _import_optimade_utils():
    """
    Lazy import of OPTIMADE utils to avoid import errors at module level.
    """
    try:
        project_root = Path(__file__).parent.parent
        database_path = project_root / "database"
        if str(database_path) not in sys.path:
            sys.path.insert(0, str(database_path))

        from optimade_database.utils import (
            fetch_structures_with_bandgap_core,
            fetch_structures_with_filter_core,
            fetch_structures_with_spg_core,
            normalize_cfr_in_filter,
            normalize_formula,
        )
        return {
            "fetch_structures_with_filter_core": fetch_structures_with_filter_core,
            "fetch_structures_with_spg_core": fetch_structures_with_spg_core,
            "fetch_structures_with_bandgap_core": fetch_structures_with_bandgap_core,
            "normalize_cfr_in_filter": normalize_cfr_in_filter,
            "normalize_formula": normalize_formula,
        }
    except ImportError as e:
        logging.error(f"Failed to import OPTIMADE utils: {e}")
        raise


class OptimadeRetriever(BaseRetriever):
    def __init__(self) -> None:
        self.data_dir = get_data_dir()
        self._utils = None

    def _get_utils(self):
        """Lazy load OPTIMADE utils."""
        if self._utils is None:
            self._utils = _import_optimade_utils()
        return self._utils

    def fetch(self, filters: Dict[str, Any], n_results: int, output_format: str) -> List[SearchResult]:
        utils = self._get_utils()
        fetch_structures_with_filter_core = utils["fetch_structures_with_filter_core"]
        fetch_structures_with_spg_core = utils["fetch_structures_with_spg_core"]
        fetch_structures_with_bandgap_core = utils["fetch_structures_with_bandgap_core"]
        normalize_cfr_in_filter = utils["normalize_cfr_in_filter"]
        normalize_formula = utils["normalize_formula"]

        # Extract filters
        formula = filters.get("formula")
        if formula:
            formula = normalize_formula(formula)

        elements = filters.get("elements") or []
        space_group = filters.get("space_group")
        band_gap = filters.get("band_gap") or {}
        filter_string = filters.get("filter_string")

        base_filter_parts: List[str] = []
        if not filter_string:
            if formula:
                base_filter_parts.append(f'chemical_formula_reduced="{formula}"')
            if elements:
                elements_str = ",".join(f'"{e}"' for e in elements)
                base_filter_parts.append(f'elements HAS ALL {elements_str}')

        base_filter = (filter_string or " AND ".join(base_filter_parts)).strip()
        base_filter = normalize_cfr_in_filter(base_filter)

        base_output_dir = self.data_dir / "mrdice_server" / "database" / "optimade_database" / "materials_data_optimade"
        as_format = [output_format] if output_format else ["cif"]
        http_timeout, total_timeout = get_optimade_timeouts()

        async def run_with_timeout(coro):
            return await asyncio.wait_for(coro, timeout=total_timeout)

        try:
            if space_group:
                fetch_result = asyncio.run(
                    run_with_timeout(
                        fetch_structures_with_spg_core(
                            base_filter=base_filter,
                            spg_number=int(space_group),
                            base_output_dir=base_output_dir,
                            as_format=as_format,
                            n_results=n_results,
                            http_timeout=http_timeout,
                        )
                    )
                )
            elif band_gap.get("min") is not None or band_gap.get("max") is not None:
                fetch_result = asyncio.run(
                    run_with_timeout(
                        fetch_structures_with_bandgap_core(
                            base_filter=base_filter,
                            min_bg=band_gap.get("min"),
                            max_bg=band_gap.get("max"),
                            base_output_dir=base_output_dir,
                            as_format=as_format,
                            n_results=n_results,
                            http_timeout=http_timeout,
                        )
                    )
                )
            else:
                fetch_result = asyncio.run(
                    run_with_timeout(
                        fetch_structures_with_filter_core(
                            filter=base_filter,
                            base_output_dir=base_output_dir,
                            as_format=as_format,
                            n_results=n_results,
                            http_timeout=http_timeout,
                        )
                    )
                )
        except asyncio.TimeoutError:
            raise MrDiceError(
                f"OPTIMADE 查询总超时 (限 {total_timeout:.0f}s)，请检查网络或稍后重试；可设置环境变量 OPTIMADE_TOTAL_TIMEOUT 调整。",
                error_type=ErrorType.NETWORK_ERROR,
                details={"total_timeout": total_timeout},
            ) from None
        except ValueError as e:
            if "could not convert string to float" in str(e):
                logging.warning(
                    "OPTIMADE provider returned non-numeric value (e.g. '-' for missing data), skipping: %s",
                    e,
                )
                return []
            raise

        cleaned_structures = fetch_result.get("cleaned_structures", []) or []
        saved_files = fetch_result.get("files", []) or []

        # Convert to SearchResult
        results: List[SearchResult] = []
        for i, struct_data in enumerate(cleaned_structures):
            attrs = struct_data.get("attributes", {})
            struct_id = struct_data.get("id", f"idx{i}")
            
            # Find corresponding file
            structure_file = None
            # Saved filenames are like: <provider_name>_<id>_<idx>.<ext>
            # `provider_url` is a full URL and won't appear in filenames, so match by id only.
            for file_path in saved_files:
                if str(struct_id) in str(file_path):
                    structure_file = file_path
                    break

            formula = attrs.get("chemical_formula_reduced") or attrs.get("chemical_formula")
            elements_list = attrs.get("elements", [])
            space_group_val = attrs.get("space_group_symbol") or attrs.get("spacegroup_symbol")
            n_atoms = attrs.get("nsites")
            band_gap_val = attrs.get("band_gap") or attrs.get("_oqmd_band_gap") or attrs.get("_gnome_bandgap")
            formation_energy = attrs.get("formation_energy_per_atom") or attrs.get("_oqmd_formation_energy_per_atom")

            results.append(
                self.create_crystal_search_result(
                    name=f"optimade_{struct_id}_{i}",
                    structure_file=structure_file,
                    formula=formula,
                    elements=elements_list,  # Already provided, don't auto-extract
                    space_group=space_group_val,
                    n_atoms=n_atoms,
                    band_gap=band_gap_val,
                    formation_energy=formation_energy,
                    source="optimade",
                    id=str(struct_id),
                )
            )

        return results

