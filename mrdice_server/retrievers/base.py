"""
Base retriever classes and protocol definitions.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from ..models.schema import normalize_result, SearchResult


class Retriever(Protocol):
    """
    Protocol defining the interface for database retrievers.
    """
    def fetch(self, filters: Dict[str, Any], n_results: int, output_format: str) -> List[SearchResult]:
        ...


class BaseRetriever:
    """
    Base class for retrievers with common utility methods.
    """

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        """
        Best-effort coercion to float for external DB values.

        - None / "" / "N/A" / "na" / "null" -> None
        - int/float -> float
        - numeric strings -> float
        - anything else -> None
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            if s.lower() in {"n/a", "na", "none", "null", "nan"}:
                return None
            try:
                return float(s)
            except Exception:
                return None
        return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        """
        Best-effort coercion to int.
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            if s.lower() in {"n/a", "na", "none", "null"}:
                return None
            try:
                return int(float(s))
            except Exception:
                return None
        return None
    
    def extract_elements_from_formula(self, formula: Optional[str]) -> List[str]:
        """
        Extract element symbols from a chemical formula.
        
        Args:
            formula: Chemical formula string (e.g., "Fe2O3", "LiFePO4")
            
        Returns:
            List of element symbols (e.g., ["Fe", "O"])
        """
        if not formula:
            return []
        
        try:
            from pymatgen.core import Composition
            comp = Composition(formula)
            return [str(e) for e in comp.elements]
        except Exception as e:
            logging.debug(f"Failed to extract elements from formula {formula}: {e}")
            return []
    
    def build_structure_file_path(
        self,
        output_dir: Path,
        name: str,
        output_format: str,
        check_exists: bool = False,
    ) -> Optional[str]:
        """
        Build structure file path based on output directory, name, and format.
        
        Args:
            output_dir: Output directory path
            name: Structure name (without extension)
            output_format: Output format ("cif", "json", etc.)
            check_exists: If True, only return path if file exists
            
        Returns:
            Full file path as string, or None if format is not supported or file doesn't exist (when check_exists=True)
        """
        if not output_format:
            return None
        
        file_path = output_dir / f"{name}.{output_format}"
        if check_exists and not file_path.exists():
            return None
        return str(file_path)
    
    def create_crystal_search_result(
        self,
        *,
        name: str,
        structure_file: Optional[str] = None,
        formula: Optional[str] = None,
        elements: Optional[List[str]] = None,
        space_group: Optional[str] = None,
        n_atoms: Optional[int] = None,
        band_gap: Optional[float] = None,
        formation_energy: Optional[float] = None,
        source: str,
        id: Optional[str] = None,
    ) -> SearchResult:
        """
        Create a SearchResult for crystal databases (Bohrium Public, OPTIMADE, OpenLAM).

        Use this when the source returns formula, elements, space_group, band_gap,
        formation_energy. If elements are not provided but formula is, elements will
        be extracted from formula automatically.

        Args:
            name: Structure name
            structure_file: Path to structure file
            formula: Chemical formula
            elements: List of element symbols (auto-extracted from formula if not provided)
            space_group: Space group symbol or number
            n_atoms: Number of atoms
            band_gap: Band gap in eV
            formation_energy: Formation energy in eV/atom
            source: Database source name (e.g. "bohriumpublic", "optimade", "openlam")
            id: Structure ID

        Returns:
            SearchResult dictionary with all fields populated where provided.
        """
        if not elements and formula:
            elements = self.extract_elements_from_formula(formula)
        band_gap = self._coerce_float(band_gap)
        formation_energy = self._coerce_float(formation_energy)
        n_atoms = self._coerce_int(n_atoms)
        return normalize_result(
            name=name,
            structure_file=structure_file,
            formula=formula,
            elements=elements or [],
            space_group=space_group,
            n_atoms=n_atoms,
            band_gap=band_gap,
            formation_energy=formation_energy,
            source=source,
            id=id,
        )

    def create_search_result_base(
        self,
        *,
        name: str,
        structure_file: Optional[str] = None,
        source: str,
        id: Optional[str] = None,
        n_atoms: Optional[int] = None,
    ) -> SearchResult:
        """
        Create a SearchResult for non-crystal databases (e.g. MOFdb).

        Returns only name, structure_file, source, id, n_atoms so the response
        does not include formula, elements, space_group, band_gap, formation_energy
        (consistent with legacy Mofdb_Server return shape).

        Args:
            name: Structure name
            structure_file: Path to structure file
            source: Database source name (e.g. "mofdbsql")
            id: Structure ID
            n_atoms: Number of atoms (optional; some MOF DBs provide it)

        Returns:
            Dict with only name, structure_file, source, id, n_atoms (no crystal fields).
        """
        n_atoms = self._coerce_int(n_atoms)
        out: SearchResult = {
            "name": name,
            "structure_file": structure_file or None,
            "source": source,
            "id": id or None,
            "n_atoms": n_atoms,
        }
        return out
