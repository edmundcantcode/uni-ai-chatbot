# backend/logic/step_runner.py
from typing import List, Dict, Any, Iterable, Tuple, Optional, Union
from cassandra.query import SimpleStatement
import logging
import sys
import re

# CRITICAL: Setup logging for this module
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s",
    stream=sys.stdout,
    force=True
)

logger = logging.getLogger(__name__)

# Constants
MAX_IN_LIST_SIZE = 200  # Cassandra's practical limit for IN clauses
DEFAULT_PAGE_SIZE = 100

# Status normalization constants
CANONICAL_ACTIVE = {"active", "enrolled", "current", "student"}

def normalize_status(s: str) -> str:
    """Normalize status strings for matching"""
    if not s:
        return ""
    return re.sub(r"[^a-z]", "", s.lower())

def get_active_status_values(session):
    """Load real active status values from database"""
    try:
        rows = session.execute("SELECT DISTINCT status FROM students")
        active_statuses = []
        
        for row in rows:
            if not row.status:
                continue
            
            normalized = normalize_status(row.status)
            if any(canonical in normalized for canonical in CANONICAL_ACTIVE):
                active_statuses.append(row.status)
        
        # Fallback if no matches found
        return active_statuses or ["Active", "Enrolled", "Current"]
        
    except Exception as e:
        logger.warning(f"Could not load status values: {e}")
        return ["Active", "Enrolled", "Current"]

class QueryOperator:
    """Supported query operators"""
    EQ = "="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    NE = "!="  # Note: Cassandra doesn't support !=, will need Python filtering
    IN = "IN"
    BETWEEN = "BETWEEN"
    CONTAINS = "CONTAINS"  # Will need Python post-processing
    LIKE = "LIKE"  # Will need Python post-processing

def chunk_ids(ids: List[int], size: int = MAX_IN_LIST_SIZE) -> Iterable[List[int]]:
    """Split large ID lists into manageable chunks"""
    for i in range(0, len(ids), size):
        yield ids[i:i+size]

def quote(v: Any) -> str:
    """Properly quote values for CQL"""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)):
        return str(v)
    # Escape single quotes for CQL
    escaped = str(v).replace("'", "''")
    return f"'{escaped}'"

def build_where_clause(where: Dict[str, Any]) -> Tuple[str, List[Any], List[str]]:
    """
    Build WHERE clause with operator support.
    
    Returns:
        - CQL where clause string
        - Parameters for prepared statement
        - List of unsupported operations that need Python filtering
    """
    clauses = []
    params = []
    python_filters = []
    
    for col, spec in where.items():
        if isinstance(spec, dict) and "op" in spec:
            op = spec["op"].upper()
            val = spec["value"]
            
            # Handle different operators
            if op == QueryOperator.IN:
                if isinstance(val, list):
                    placeholders = ", ".join(["?"] * len(val))
                    clauses.append(f"{col} IN ({placeholders})")
                    params.extend(val)
                else:
                    clauses.append(f"{col} = ?")
                    params.append(val)
                    
            elif op == QueryOperator.BETWEEN:
                if isinstance(val, list) and len(val) == 2:
                    clauses.append(f"{col} >= ? AND {col} <= ?")
                    params.extend(val)
                else:
                    logger.warning(f"BETWEEN requires 2 values, got {val}")
                    
            elif op in [QueryOperator.GT, QueryOperator.GTE, QueryOperator.LT, 
                       QueryOperator.LTE]:
                clauses.append(f"{col} {op} ?")
                params.append(val)
                
            elif op in [QueryOperator.NE, QueryOperator.CONTAINS, QueryOperator.LIKE]:
                # These need Python post-processing (Cassandra doesn't support != directly)
                python_filters.append({
                    "column": col,
                    "op": op,
                    "value": val
                })
                
            else:  # Default to equality
                clauses.append(f"{col} = ?")
                params.append(val)
        else:
            # Legacy format - assume equality
            if isinstance(spec, list):
                placeholders = ", ".join(["?"] * len(spec))
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(spec)
            else:
                clauses.append(f"{col} = ?")
                params.append(spec)
    
    where_clause = " AND ".join(clauses) if clauses else "1=1"
    return where_clause, params, python_filters

def apply_python_filters(rows: List[Dict[str, Any]], filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply Python-based filtering for operations not supported by Cassandra"""
    if not filters:
        return rows
    
    filtered_rows = []
    for row in rows:
        include_row = True
        
        for f in filters:
            col = f["column"]
            op = f["op"]
            val = f["value"]
            row_val = row.get(col)
            
            if op == QueryOperator.NE:
                if row_val == val:
                    include_row = False
                    break
                    
            elif op == QueryOperator.CONTAINS:
                if row_val is None or str(val).lower() not in str(row_val).lower():
                    include_row = False
                    break
                    
            elif op == QueryOperator.LIKE:
                # Simple LIKE implementation (% wildcards)
                pattern = val.replace("%", ".*").replace("_", ".")
                if row_val is None or not re.match(pattern, str(row_val), re.IGNORECASE):
                    include_row = False
                    break
        
        if include_row:
            filtered_rows.append(row)
    
    return filtered_rows

def execute_query_once(session, table: str, select_cols: List[str], 
                      where_clause: str, params: List[Any], 
                      limit: Optional[int], allow_filtering: bool,
                      offset: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Execute a single CQL query with proper error handling"""
    
    # Build CQL query
    select_str = ", ".join(select_cols) if select_cols else "*"
    limit_clause = f" LIMIT {limit}" if limit else ""
    allow_clause = " ALLOW FILTERING" if allow_filtering else ""
    
    cql = f"SELECT {select_str} FROM {table} WHERE {where_clause}{limit_clause}{allow_clause}"
    
    # 🔥 CRITICAL LOGGING: Log the exact CQL and params
    logger.info("CQL ▶ %s params=%s", cql, params)
    
    # Execute query with auto-retry
    warnings = []
    try:
        if params:
            prepared = session.prepare(cql)
            result = session.execute(prepared, params)
        else:
            result = session.execute(SimpleStatement(cql))
        
        # 🔧 CRITICAL FIX: Convert to list immediately and store in separate variable
        raw_rows = list(result)
        
        if hasattr(result, 'warnings') and result.warnings:
            warnings = result.warnings
            
    except Exception as e:
        # AUTO-RETRY with ALLOW FILTERING if that's the only issue
        from cassandra import InvalidRequest
        if (isinstance(e, InvalidRequest) and 
            "ALLOW FILTERING" in str(e) and 
            not allow_filtering):
            
            logger.info(f"🔄 Auto-retrying with ALLOW FILTERING for table {table}")
            return execute_query_once(session, table, select_cols, where_clause, 
                                    params, limit, True, offset)  # Retry with allow_filtering=True
        
        logger.error(f"Query execution failed: {e}")
        raise
    
    # 🔧 CRITICAL FIX: Convert to list of dicts using raw_rows (NOT result)
    rows = []
    for r in raw_rows:
        row_dict = {}
        for col in r._fields:
            val = getattr(r, col)
            if val is None:
                row_dict[col] = None
            elif isinstance(val, (int, float, bool)):
                row_dict[col] = val
            else:
                row_dict[col] = str(val)
        rows.append(row_dict)
    
    # 🔧 SPECIAL HANDLING: Detect COUNT queries and extract count value
    is_count_query = any("COUNT(" in str(col).upper() for col in select_cols)
    count_value = None
    
    if is_count_query and rows:
        # Cassandra returns COUNT as 'count' column
        count_value = rows[0].get('count', 0)
        logger.info(f"COUNT query result: {count_value}")
    
    # 🔥 CRITICAL LOGGING: Log the row count returned
    logger.info("ROWS ◀ %d for table=%s select=%s where=%s", 
               len(rows), table, select_cols, where_clause)
    
    metadata = {
        "row_count": len(rows),
        "warnings": warnings,
        "cql": cql,
        "truncated": limit and len(rows) == limit,
        "is_count_query": is_count_query,
        "count_value": count_value
    }
    
    return rows, metadata

def run_step(session, step: Dict[str, Any], id_pool: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """
    Execute a query step with enhanced operator support and chunking.
    """
    
    # 🔥 CRITICAL LOGGING: Log the incoming step
    logger.info("STEP ▶ table=%s select=%s where=%s limit=%s", 
               step.get("table"), step.get("select"), step.get("where"), step.get("limit"))
    
    # Extract step components
    table = step["table"]
    select_cols = step.get("select", ["*"])
    where = dict(step.get("where", {}))
    limit = step.get("limit")
    offset = step.get("offset", 0)
    allow_filtering = step.get("allow_filtering", False)
    
    # Handle ID pool from previous step
    if step.get("where_in_ids_from_step") is not None and id_pool is not None:
        where["id"] = {"op": "IN", "value": id_pool}
    
    # 🔧 STATUS NORMALIZATION: If filtering by status with our hardcoded values, try to get real ones
    if "status" in where:
        status_spec = where["status"]
        if isinstance(status_spec, dict) and status_spec.get("op") == "IN":
            hardcoded_active = ["Active", "Enrolled", "Current"]
            if status_spec.get("value") == hardcoded_active:
                try:
                    real_active_statuses = get_active_status_values(session)
                    where["status"]["value"] = real_active_statuses
                    logger.info(f"🔄 Updated status filter to real values: {real_active_statuses}")
                except Exception as e:
                    logger.warning(f"Could not load real status values: {e}")
    
    # Build WHERE clause with operator support
    where_clause, params, python_filters = build_where_clause(where)
    
    # Check if we need to chunk large IN lists
    needs_chunking = False
    chunk_column = None
    chunk_values = []
    
    for col, spec in where.items():
        if isinstance(spec, dict) and spec.get("op") == "IN":
            values = spec.get("value", [])
            if len(values) > MAX_IN_LIST_SIZE:
                needs_chunking = True
                chunk_column = col
                chunk_values = values
                break
    
    all_rows = []
    total_metadata = {
        "row_count": 0,
        "warnings": [],
        "cql_queries": [],
        "truncated": False,
        "is_count_query": False,
        "count_value": None
    }
    
    if needs_chunking:
        # Execute in chunks
        logger.info(f"Chunking {len(chunk_values)} IDs into batches of {MAX_IN_LIST_SIZE}")
        
        for chunk in chunk_ids(chunk_values, MAX_IN_LIST_SIZE):
            # Update where clause for this chunk
            chunk_where = dict(where)
            chunk_where[chunk_column] = {"op": "IN", "value": chunk}
            
            chunk_where_clause, chunk_params, _ = build_where_clause(chunk_where)
            
            rows, metadata = execute_query_once(
                session, table, select_cols, chunk_where_clause, 
                chunk_params, limit, allow_filtering, offset
            )
            
            all_rows.extend(rows)
            total_metadata["warnings"].extend(metadata["warnings"])
            total_metadata["cql_queries"].append(metadata["cql"])
            
            # Handle count queries across chunks
            if metadata["is_count_query"]:
                if total_metadata["count_value"] is None:
                    total_metadata["count_value"] = 0
                total_metadata["count_value"] += metadata["count_value"] or 0
                total_metadata["is_count_query"] = True
            
            # Stop if we've hit the limit
            if limit and len(all_rows) >= limit:
                all_rows = all_rows[:limit]
                total_metadata["truncated"] = True
                break
    else:
        # Execute single query
        rows, metadata = execute_query_once(
            session, table, select_cols, where_clause, 
            params, limit, allow_filtering, offset
        )
        all_rows = rows
        total_metadata.update(metadata)
    
    # Apply Python filters if needed
    if python_filters:
        logger.info(f"Applying {len(python_filters)} Python filters")
        all_rows = apply_python_filters(all_rows, python_filters)
        total_metadata["python_filtered"] = True
        total_metadata["python_filters"] = python_filters
    
    # 🔧 CRITICAL FIX: Handle COUNT(*) queries properly
    is_count_query = any("COUNT(" in str(col).upper() for col in select_cols)
    if is_count_query:
        count_val = all_rows[0].get('count', 0) if all_rows else 0
        logger.info(f"COUNT query result: {count_val}")
        total_metadata["count_value"] = count_val
        total_metadata["is_count_query"] = True
        # Return structured count result
        return [{"count": count_val}], {**total_metadata, "count": count_val}
    
    # Log warnings
    if total_metadata["warnings"]:
        for warning in total_metadata["warnings"]:
            logger.warning(f"Cassandra warning: {warning}")
    
    # 🔥 FINAL LOGGING: Log what we're returning
    logger.info("STEP ◀ returning %d rows for table=%s (count_value=%s)", 
               len(all_rows), table, total_metadata.get("count_value"))
    
    return all_rows

def validate_step(step: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate step structure and return errors"""
    errors = []
    
    if "table" not in step:
        errors.append("Missing required field: table")
    
    # Validate where clause operators
    where = step.get("where", {})
    for col, spec in where.items():
        if isinstance(spec, dict) and "op" in spec:
            op = spec.get("op", "").upper()
            if op not in ["=", ">", ">=", "<", "<=", "!=", "IN", "BETWEEN", "CONTAINS", "LIKE"]:
                errors.append(f"Unknown operator '{op}' for column '{col}'")
            
            if op == "BETWEEN":
                val = spec.get("value", [])
                if not isinstance(val, list) or len(val) != 2:
                    errors.append(f"BETWEEN operator requires exactly 2 values for column '{col}'")
    
    return len(errors) == 0, errors

# Export enhanced functionality
__all__ = [
    'run_step',
    'validate_step',
    'QueryOperator',
    'MAX_IN_LIST_SIZE',
    'DEFAULT_PAGE_SIZE',
    'get_active_status_values',
    'normalize_status'
]