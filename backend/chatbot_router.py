# backend/chatbot_router.py

from fastapi import APIRouter
from pydantic import BaseModel
from backend.llm.generate_cql import generate_cql_from_query
from backend.database.connect_cassandra import session
from backend.utils.student_check import resolve_name_to_id
from backend.utils.fuzzy_matcher import patch_fuzzy_values
from fastapi.responses import JSONResponse
from cassandra.util import SortedSet, OrderedMapSerializedKey
import re
import collections.abc

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

# 🔍 Extract capitalized names like "Bob Johnson"
def extract_name_if_present(text: str):
    match = re.search(r"\b([A-Z][a-z]+\s[A-Z][a-z]+)\b", text)
    return match.group(1) if match else None

# 🔧 Recursively convert anything to JSON-safe types
def deep_convert(obj):
    if isinstance(obj, dict):
        return {str(deep_convert(k)): deep_convert(v) for k, v in obj.items()}
    elif isinstance(obj, (SortedSet, OrderedMapSerializedKey, set, frozenset)):
        return [deep_convert(item) for item in obj]
    elif isinstance(obj, list):
        return [deep_convert(item) for item in obj]
    elif hasattr(obj, "_asdict"):
        return deep_convert(obj._asdict())
    elif hasattr(obj, "__dict__"):
        return deep_convert(vars(obj))
    return obj

# 🔧 Flatten list-of-dict fields like subjects or qualifications
def flatten_nested_fields(row):
    flat_row = {}
    for k, v in row.items():
        if isinstance(v, list) and all(isinstance(i, dict) for i in v):
            for i, item in enumerate(v):
                for subkey, subval in item.items():
                    flat_row[f"{k}_{i}_{subkey}"] = subval
        else:
            flat_row[k] = v
    return flat_row

# 🔧 Fully clean each row for JSON serialization
def clean_row(row):
    raw = deep_convert(row)
    return flatten_nested_fields(raw)

@router.post("/chatbot")
async def chatbot_endpoint(payload: QueryRequest):
    try:
        user_query = payload.query.strip()
        processed_query = user_query

        # Step 0: Try fuzzy name → ID
        name = extract_name_if_present(user_query)
        if name:
            resolved_id = resolve_name_to_id(name)
            if resolved_id:
                processed_query = user_query.replace(name, str(resolved_id))

        # Step 1: Generate CQL using LLM
        cql = generate_cql_from_query(processed_query)
        print("▶️ CQL:", cql)

        # Step 2: Patch illegal subquery syntax (e.g. SELECT id FROM students ...)
        if "SELECT id FROM students" in cql:
            print("⚠️ Detected unsupported subquery. Attempting patch...")
            match = re.search(r"name\s*=\s*'([^']+)'", cql)
            if match:
                name = match.group(1)
                id_result = session.execute(
                    f"SELECT id FROM students WHERE name = '{name}' ALLOW FILTERING"
                ).one()
                if id_result:
                    student_id = id_result.id
                    fixed_cql = re.sub(r"IN\s*\(SELECT id FROM students.*?\)", f"= {student_id}", cql)
                    fixed_cql = re.sub(r"\s+AND\s+id\s+IS\s+NOT\s+NULL", "", fixed_cql, flags=re.IGNORECASE)
                    print("🔁 Patched CQL:", fixed_cql)
                    cql = fixed_cql
                else:
                    raise ValueError(f"❌ Student '{name}' not found.")
            else:
                raise ValueError("❌ Could not extract name from subquery.")

        # Step 3: Append ALLOW FILTERING if needed
        if "WHERE" in cql.upper() and "ALLOW FILTERING" not in cql.upper():
            print("⚠️ Query might need ALLOW FILTERING. Appending it.")
            cql += " ALLOW FILTERING"

        # Step 4: Execute query on Cassandra
        rows = session.execute(cql)
        result = [clean_row(row) for row in rows]

        # Step 5: Return response
        return JSONResponse(content={
            "query": user_query,
            "processed_query": processed_query,
            "cql": cql,
            "result": result
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)