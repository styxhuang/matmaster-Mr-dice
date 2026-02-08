import json
import logging
import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .base import BaseRetriever
from ..core.config import get_data_dir
from ..models.schema import SearchResult


def _import_mofdb_utils():
    """
    Lazy import of MOFdb SQL utils to avoid import errors at module level.
    """
    try:
        project_root = Path(__file__).parent.parent
        database_path = project_root / "database"
        if str(database_path) not in sys.path:
            sys.path.insert(0, str(database_path))

        from mofdbsql_database.utils import (
            validate_sql_security,
            save_mofs,
            tag_from_filters,
            base_data_dir,
            build_output_stem,
        )
        return {
            "validate_sql_security": validate_sql_security,
            "save_mofs": save_mofs,
            "tag_from_filters": tag_from_filters,
            "build_output_stem": build_output_stem,
            "base_data_dir": base_data_dir,
        }
    except ImportError as e:
        logging.error(f"Failed to import MOFdb SQL utils: {e}")
        raise


class MofdbSqlRetriever(BaseRetriever):
    def __init__(self) -> None:
        self.data_dir = get_data_dir()
        self._utils = None
        self._db_path = None

    def _get_utils(self):
        """Lazy load MOFdb utils."""
        if self._utils is None:
            self._utils = _import_mofdb_utils()
        return self._utils

    def _get_db_path(self) -> Path:
        """Get MOFdb SQLite database path from environment variable."""
        if self._db_path is None:
            import os

            db_path = os.getenv("MOFDB_SQL_DB_PATH")
            if not db_path:
                raise RuntimeError("MOFDB_SQL_DB_PATH is not set in environment (.env)")

            self._db_path = Path(db_path)
        return self._db_path

    def fetch(self, filters: Dict[str, Any], n_results: int, output_format: str) -> List[SearchResult]:
        utils = self._get_utils()
        validate_sql_security = utils["validate_sql_security"]
        save_mofs = utils["save_mofs"]
        tag_from_filters = utils["tag_from_filters"]
        build_output_stem = utils["build_output_stem"]
        base_data_dir = utils.get("base_data_dir")

        # Extract SQL query from filters
        sql_query = filters.get("sql_query")
        if not sql_query:
            # If no SQL query, construct a simple query from other filters
            sql_query = self._build_sql_from_filters(filters, n_results)
        else:
            # Validate SQL security
            validate_sql_security(sql_query)
            # Add LIMIT if not present
            if "LIMIT" not in sql_query.upper():
                sql_query = f"{sql_query.rstrip(';')} LIMIT {n_results}"

        # Execute SQL query
        db_path = self._get_db_path()
        if not db_path.exists():
            logging.error(f"MOFdb SQLite database not found at {db_path}")
            return []

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            conn.close()

            # Convert rows to dicts
            items = [dict(row) for row in rows]
        except Exception as exc:
            logging.error(f"MOFdb SQL query failed: {exc}")
            return []

        # Save structures
        filter_str = sql_query
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_hash = hashlib.sha1(filter_str.encode("utf-8")).hexdigest()[:8]
        output_dir = (
            self.data_dir
            / "mrdice_server"
            / "database"
            / "mofdbsql_database"
            / "materials_data_mofdb"
            / f"sql_query_{ts}_{short_hash}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        output_formats = [output_format] if output_format else ["cif", "json"]
        try:
            # Temporarily set base_data_dir for save_mofs
            import mofdbsql_database.utils as mofdb_utils
            original_base_data_dir = mofdb_utils.base_data_dir
            if base_data_dir:
                mofdb_utils.base_data_dir = base_data_dir
            
            items, warnings = save_mofs(
                items=items,
                output_dir=output_dir,
                output_formats=output_formats,
            )
            
            # Restore original base_data_dir
            mofdb_utils.base_data_dir = original_base_data_dir
            if warnings:
                for warning in warnings:
                    logging.warning(f"MOFdb save warning: {warning}")
        except Exception as exc:
            logging.error(f"MOFdb save failed: {exc}")

        # Convert to SearchResult
        results: List[SearchResult] = []
        for i, mof in enumerate(items):
            mof_id = mof.get("id") or mof.get("mofid") or f"idx{i}"
            name = mof.get("name") or f"mof_{mof_id}_{i}"
            # Determine structure file path.
            # MOF files are written by `save_mofs` using a stem derived from
            # provider + identifier + index. Reconstruct the same stem here
            # so we can point SearchResult.structure_file to the actual file.
            structure_file = None
            if output_format:
                stem = build_output_stem(mof, i)
                candidate = output_dir / f"{stem}.{output_format}"
                if candidate.exists():
                    structure_file = str(candidate)

            # MOF: use minimal result shape (no formula, elements, space_group, band_gap,
            # formation_energy) to match legacy Mofdb_Server return.
            results.append(
                self.create_search_result_base(
                    name=name,
                    structure_file=structure_file,
                    source="mofdbsql",
                    id=str(mof_id),
                    n_atoms=mof.get("n_atom"),
                )
            )

        return results

    def _build_sql_from_filters(self, filters: Dict[str, Any], n_results: int) -> str:
        """
        Build a simple SQL query from filters when no sql_query is provided.
        """
        conditions = []
        
        formula = filters.get("formula")
        elements = filters.get("elements")
        database = filters.get("database")
        
        if formula:
            # Map formula filter to name column to avoid referencing non-existent formula column
            conditions.append(f"name LIKE '%{formula}%'")
        
        if elements:
            # Simple element matching: require all elements to appear in `elements` table
            # mofs.id IN (SELECT mof_id FROM elements WHERE element_symbol = 'X')
            element_conditions = [
                f"id IN (SELECT mof_id FROM elements WHERE element_symbol = '{elem}')"
                for elem in elements
            ]
            if element_conditions:
                conditions.append(f"({' AND '.join(element_conditions)})")
        
        if database:
            conditions.append(f"database = '{database}'")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM mofs {where_clause} LIMIT {n_results}"
        
        return sql

