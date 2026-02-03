import json
import logging
import re
from pathlib import Path
from typing import List, Literal, TypedDict, Any

Format = Literal["cif", "json"]

# base_data_dir = Path("/home/MOF_SQL_test/data/original")
base_data_dir = Path("/home/MOF_SQL_test/data/original")

MOFDB_DROP_ATTRS = {
    "cif", 
    "json_repr", 
    "isotherms", 
    "heats",
    "isotherms_filtered",
    "heats_filtered",
}

from typing import Optional

def validate_sql_security(sql: str) -> None:
    """
    验证SQL语句的安全性，只允许SELECT和WITH查询
    
    Args:
        sql: SQL查询语句
        
    Raises:
        ValueError: 如果SQL语句包含危险操作
    """
    sql_upper = sql.strip().upper()
    
    # 检查是否以SELECT或WITH开头（CTE查询）
    if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
        raise ValueError("安全限制：只允许SELECT或WITH查询语句")
    
    # 检查是否包含危险的关键字
    dangerous_keywords = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 
        'TRUNCATE', 'REPLACE', 'MERGE', 'EXEC', 'EXECUTE', 'CALL',
        'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK', 'SAVEPOINT'
    ]
    
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            raise ValueError(f"安全限制：不允许包含 {keyword} 关键字")
    
    # 系统表和系统函数访问已允许

def tag_from_filters(
    mofid: Optional[str] = None,
    mofkey: Optional[str] = None,
    name: Optional[str] = None,
    database: Optional[str] = None,
    vf_min: Optional[float] = None,
    vf_max: Optional[float] = None,
    lcd_min: Optional[float] = None,
    lcd_max: Optional[float] = None,
    pld_min: Optional[float] = None,
    pld_max: Optional[float] = None,
    sa_m2g_min: Optional[float] = None,
    sa_m2g_max: Optional[float] = None,
    sa_m2cm3_min: Optional[float] = None,
    sa_m2cm3_max: Optional[float] = None,
    max_len: int = 40
) -> str:
    """
    Build a short tag string from MOFdb filter parameters for naming output folders.
    """
    parts = []

    if mofid:
        parts.append(f"id{mofid[:8]}")   # 避免太长，截取前8位
    if mofkey:
        parts.append(f"key{mofkey[:8]}")
    if name:
        parts.append(name.replace(" ", "_"))
    if database:
        parts.append(database.replace(" ", ""))

    if vf_min is not None or vf_max is not None:
        parts.append(f"vf{vf_min or ''}-{vf_max or ''}")
    if lcd_min is not None or lcd_max is not None:
        parts.append(f"lcd{lcd_min or ''}-{lcd_max or ''}")
    if pld_min is not None or pld_max is not None:
        parts.append(f"pld{pld_min or ''}-{pld_max or ''}")
    if sa_m2g_min is not None or sa_m2g_max is not None:
        parts.append(f"sa_g{sa_m2g_min or ''}-{sa_m2g_max or ''}")
    if sa_m2cm3_min is not None or sa_m2cm3_max is not None:
        parts.append(f"sa_cm3{sa_m2cm3_min or ''}-{sa_m2cm3_max or ''}")

    tag = "_".join(str(p) for p in parts if p)
    return tag[:max_len] or "mofdb"


def _safe_basename(text: str, max_len: int = 80) -> str:
    """
    Make a safe, reasonably short filename stem.
    """
    text = str(text) if text is not None else "mof"
    # Replace slashes and spaces
    text = text.replace("/", "_").replace("\\", "_").replace(" ", "_")
    # Keep only safe characters
    text = re.sub(r"[^A-Za-z0-9._-]", "_", text)
    # Collapse multiple underscores
    text = re.sub(r"_+", "_", text).strip("_")
    # Limit length
    return text[:max_len] or "mof"


def _pick_identifier(mof: Any, idx: int) -> str:
    """
    Prefer name -> mofkey -> mofid -> id -> idx for file naming.
    """
    ident = (
        mof.get("name", None)
        or mof.get("mofkey", None)
        or mof.get("mofid", None)
        or mof.get("id", None)
        or f"idx{idx}"
    )
    return _safe_basename(ident, max_len=20)


def _provider(mof: Any) -> str:
    """
    Use database as provider tag; fallback to 'mofdb'.
    """
    prov = mof.get("database", None) or "mofdb"
    return _safe_basename(prov)


def save_mofs(
    items: List[Any],
    output_dir: Path,
    output_formats: List[Format] = ["cif", "json"]
) -> tuple[List[dict], List[str]]:
    """
    Save user requested file formats, return query results and warnings.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = []
    
    for i, mof in enumerate(items):
        prov = _provider(mof)
        ident = _pick_identifier(mof, i)
        stem = _safe_basename(f"{prov}_{ident}_{i}")
        
        cif_path = mof.get('cif_path')
        
        if cif_path:
            # Has cif_path: copy original files
            full_cif_path = base_data_dir / cif_path
            base_path = full_cif_path.parent
            base_name = full_cif_path.stem
            
            for format_type in output_formats:
                if format_type == 'cif':
                    src_file = full_cif_path
                    dst_file = output_dir / f"{stem}.cif"
                elif format_type == 'json':
                    json_path = base_path / f"{base_name}.json"
                    src_file = json_path
                    dst_file = output_dir / f"{stem}.json"
                else:
                    continue
                
                if src_file.exists():
                    try:
                        if format_type == 'json':
                            # Reformat JSON for better readability
                            with open(src_file, 'r', encoding='utf-8') as src_f:
                                data = json.load(src_f)
                            with open(dst_file, 'w', encoding='utf-8') as dst_f:
                                json.dump(data, dst_f, indent=2, ensure_ascii=False)
                        else:
                            import shutil
                            shutil.copy2(src_file, dst_file)
                    except Exception as e:
                        logging.error(f"Failed to copy {format_type} file for {ident}: {e}")
                else:
                    warning_msg = f"Source file not found: {src_file} for {ident}"
                    logging.warning(warning_msg)
                    warnings.append(warning_msg)
        else:
            # No cif_path: try to construct path based on database and name
            database = mof.get("database", "")
            name = mof.get("name", "")
            
            # Only try to construct path if we have a valid name (not idx0, idx1, etc.) and database
            constructed_cif_path = None
            if name and not name.startswith("idx") and database:
                # Construct path based on database type
                if "CoREMOF 2014" in database:
                    constructed_cif_path = f"core2014/{name}.cif"
                elif "CoREMOF 2019" in database:
                    constructed_cif_path = f"core2019/{name}.cif"
                elif "hMOF" in database:
                    constructed_cif_path = f"hmof/{name}.cif"
                elif "IZA" in database:
                    constructed_cif_path = f"iza/{name}.cif"
                elif "Tobacco" in database:
                    constructed_cif_path = f"tobacco/{name}.cif"
                elif "PCOD-syn" in database:
                    constructed_cif_path = f"pcod/{name}.cif"
            
            if constructed_cif_path:
                full_cif_path = base_data_dir / constructed_cif_path
                
                # Try to copy original files if they exist
                for format_type in output_formats:
                    if format_type == 'cif':
                        src_file = full_cif_path
                        dst_file = output_dir / f"{stem}.cif"
                    elif format_type == 'json':
                        json_path = full_cif_path.with_suffix('.json')
                        src_file = json_path
                        dst_file = output_dir / f"{stem}.json"
                    else:
                        continue
                    
                    if src_file.exists():
                        try:
                            if format_type == 'json':
                                # Reformat JSON for better readability
                                with open(src_file, 'r', encoding='utf-8') as src_f:
                                    data = json.load(src_f)
                                with open(dst_file, 'w', encoding='utf-8') as dst_f:
                                    json.dump(data, dst_f, indent=2, ensure_ascii=False)
                            else:
                                import shutil
                                shutil.copy2(src_file, dst_file)
                        except Exception as e:
                            logging.error(f"Failed to copy {format_type} file for {ident}: {e}")
                    else:
                        warning_msg = f"Source file not found: {src_file} for {ident}"
                        logging.warning(warning_msg)
                        warnings.append(warning_msg)
            else:
                # No path construction possible: save query result as JSON
                if "json" in output_formats:
                    json_file = output_dir / f"{stem}.json"
                    try:
                        with open(json_file, "w", encoding="utf-8") as f:
                            json.dump(mof, f, indent=2, ensure_ascii=False)
                    except Exception as e:
                        logging.error(f"Failed to save JSON file for {ident}: {e}")
                
                # Check if user requested CIF but result has no cif_path
                if 'cif' in output_formats:
                    warning_msg = f"Result {i} ({ident}): User requested CIF format but no cif_path found in query result"
                    logging.warning(warning_msg)
                    warnings.append(warning_msg)
                    # Since CIF is not available, save query result as JSON instead
                    json_file = output_dir / f"{stem}.json"
                    try:
                        with open(json_file, "w", encoding="utf-8") as f:
                            json.dump(mof, f, indent=2, ensure_ascii=False)
                    except Exception as e:
                        logging.error(f"Failed to save JSON file for {ident}: {e}")
    
    # Return query results directly without any processing
    return items, warnings

