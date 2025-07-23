# backend/logic/step_runner.py
from typing import List, Dict, Any, Iterable, Tuple, Optional, Union
from cassandra.query import SimpleStatement
import logging

logger = logging.getLogger(__name__)

# Constants
MAX_IN_LIST_SIZE = 200  # Cassandra's practical limit for IN clauses
DEFAULT_PAGE_SIZE = 100

class QueryOperator:
    """Supported query operators"""
    EQ = "="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    NE = "!="
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
                       QueryOperator.LTE, QueryOperator.NE]:
                clauses.append(f"{col} {op} ?")
                params.append(val)
                
            elif op in [QueryOperator.CONTAINS, QueryOperator.LIKE]:
                # These need Python post-processing
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
            
            if op == QueryOperator.CONTAINS:
                if row_val is None or str(val).lower() not in str(row_val).lower():
                    include_row = False
                    break
                    
            elif op == QueryOperator.LIKE:
                # Simple LIKE implementation (% wildcards)
                import re
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
    
    # Log for debugging
    logger.debug(f"Executing CQL: {cql}")
    logger.debug(f"With params: {params}")
    
    # Execute query with auto-retry
    warnings = []
    try:
        if params:
            prepared = session.prepare(cql)
            result = session.execute(prepared, params)
        else:
            result = session.execute(SimpleStatement(cql))
        
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
    
    # Convert to list of dicts (rest of function stays the same)
    rows = []
    for r in result:
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
    
    metadata = {
        "row_count": len(rows),
        "warnings": warnings,
        "cql": cql,
        "truncated": limit and len(rows) == limit
    }
    
    return rows, metadata

def run_step(session, step: Dict[str, Any], id_pool: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """
    Execute a query step with enhanced operator support and chunking.
    
    Step format:
    {
        "table": "students",
        "select": ["id", "name", "overallcgpa"],
        "where": {
            "overallcgpa": {"op": ">", "value": 3.0},
            "programme": {"op": "IN", "value": ["CS", "IT"]},
            "name": {"op": "CONTAINS", "value": "John"}  # Python filter
        },
        "limit": 100,
        "offset": 0,  # For pagination
        "allow_filtering": true,
        "where_in_ids_from_step": 0  # Use IDs from previous step
    }
    """
    
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
        "truncated": False
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
        total_metadata = metadata
    
    # Apply Python filters if needed
    if python_filters:
        logger.info(f"Applying {len(python_filters)} Python filters")
        all_rows = apply_python_filters(all_rows, python_filters)
        total_metadata["python_filtered"] = True
        total_metadata["python_filters"] = python_filters
    
    # Log warnings
    if total_metadata["warnings"]:
        for warning in total_metadata["warnings"]:
            logger.warning(f"Cassandra warning: {warning}")
    
    # Store metadata in rows (optional - for debugging)
    if all_rows and logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Query returned {len(all_rows)} rows")
        logger.debug(f"Metadata: {total_metadata}")
    
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
    'DEFAULT_PAGE_SIZE'
]