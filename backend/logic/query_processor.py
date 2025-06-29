import re
from fastapi.responses import JSONResponse
from backend.llm.generate_cql import generate_cql_from_query
from backend.database.connect_cassandra import session
from backend.utils.student_check import resolve_name_to_id
from backend.utils.fuzzy_matcher import patch_fuzzy_values
from cassandra.util import SortedSet, OrderedMapSerializedKey

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

def clean_row(row):
    raw = deep_convert(row)
    return flatten_nested_fields(raw)

def extract_name_if_present(text: str):
    match = re.search(r"\b([A-Z][a-z]+\s[A-Z][a-z]+)\b", text)
    return match.group(1) if match else None

async def handle_chatbot_query(user_query: str):
    processed_query = user_query.strip()
    name = extract_name_if_present(user_query)

    # ✅ Shortcut: Subject query with student name → Force ID
    if name and "subject" in user_query.lower():
        resolved_id = resolve_name_to_id(name)
        if resolved_id:
            cql = f"SELECT * FROM subjects WHERE id = {resolved_id} ALLOW FILTERING"
            rows = session.execute(cql)
            result = [clean_row(row) for row in rows]
            return JSONResponse({
                "query": user_query,
                "processed_query": processed_query,
                "cql": cql,
                "result": result
            })

    for retry in range(10):
        try:
            # 🔁 Retry with name forced into query
            if name and retry > 0:
                resolved_id = resolve_name_to_id(name)
                if resolved_id:
                    processed_query = re.sub(name, str(resolved_id), processed_query, flags=re.IGNORECASE)

            cql = generate_cql_from_query(processed_query)

            # 🛡️ Protect against invalid CQLs
            if ";" in cql and cql.count(";") > 1:
                raise ValueError("Multiple CQL statements detected")
            cql = re.sub(r"\bFROMM\b", "FROM", cql, flags=re.IGNORECASE)
            cql = re.sub(r"\bSELECTT\b", "SELECT", cql, flags=re.IGNORECASE)

            # 🔄 Handle broken subquery pattern like WHERE id = (SELECT...)
            if re.search(r"id\s*=\s*\(\s*SELECT", cql, re.IGNORECASE):
                name_match = re.search(r"WHERE name\s*=\s*'([^']+)'", cql, re.IGNORECASE)
                if name_match:
                    name_str = name_match.group(1)
                    id_rows = session.execute(f"SELECT id FROM students WHERE name = '{name_str}' ALLOW FILTERING")
                    rows = list(id_rows)
                    if not rows:
                        return JSONResponse({"error": f"No ID found for name '{name_str}'"}, status_code=404)
                    id = rows[0].id
                    cql = f"SELECT * FROM subjects WHERE id = {id} ALLOW FILTERING"

            # ✅ Run and clean results
            if "WHERE" in cql.upper() and "ALLOW FILTERING" not in cql.upper():
                cql += " ALLOW FILTERING"

            rows = session.execute(cql)
            result = [clean_row(row) for row in rows]
            result = [dict(t) for t in {tuple(sorted(d.items())) for d in result}]  # Deduplicate

            # 🎯 Handle special one-column outputs like financialaid
            if result and isinstance(result[0], dict) and "financialaid" in result[0]:
                all_values = []
                for row in result:
                    raw = row["financialaid"]
                    all_values.extend([x.strip() for x in raw.split(",") if x.strip()])
                result = [{"financialaid": val} for val in sorted(set(all_values))]

            # 📌 NO LONGER showing: "The id is X"
            # Always return as result

            return JSONResponse({
                "query": user_query,
                "processed_query": processed_query,
                "cql": cql,
                "result": result
            })

        except Exception as e:
            if retry == 9:
                return JSONResponse({"error": str(e)}, status_code=500)
