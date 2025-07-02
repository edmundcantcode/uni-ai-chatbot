import re
from fastapi.responses import JSONResponse
from backend.llm.generate_cql import generate_cql_from_query
from backend.database.connect_cassandra import session
from backend.utils.student_check import resolve_name_to_id, resolve_all_ids_by_name
from backend.utils.fuzzy_matcher import patch_fuzzy_values
from backend.logic.verifier import attach_llm_verification
from cassandra.util import SortedSet, OrderedMapSerializedKey
from backend.utils.unique_values_loader import get_all_non_name_values
from backend.utils.name_extractor import extract_name_spacy as extract_name_if_present

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

async def handle_chatbot_query(user_query: str, userid: str, role: str):
    # 🛑 Block invalid admin queries
    if role == "admin" and "my" in user_query.lower():
        return JSONResponse({"error": "❌ 'My' queries are not allowed for admin."}, status_code=400)

    # 🔒 Restrict student access
    if role == "student":
        id_in_query = re.search(r"\b\d{5,}\b", user_query)
        name = extract_name_if_present(user_query)

        if id_in_query and id_in_query.group() != userid:
            return JSONResponse({"error": "❌ You can only access your own data."}, status_code=403)

        if name:
            matches = resolve_all_ids_by_name(name)
            if not any(str(row["id"]) == userid for row in matches):
                return JSONResponse({"error": "❌ You can only access your own data."}, status_code=403)

        user_query = re.sub(r"\bmy\b", f"{userid}'s", user_query, flags=re.IGNORECASE)

    # ✅ Begin normal query handling
    processed_query = user_query.strip()
    name = extract_name_if_present(user_query)
    non_name_values = get_all_non_name_values()

    if name:
        folded_name = name.casefold()
        folded_values = {val.casefold() for val in non_name_values if isinstance(val, str)}

        if folded_name in folded_values:
            print(f"⚠️ Skipping name '{name}' since it's a known value like awardclassification/country.")
            name = None


    print("🔍 Extracted name:", name)

    if name:
        matched = resolve_all_ids_by_name(name)

        if not matched:
            return JSONResponse({"error": f"No student found named '{name}'"}, status_code=404)

        if len(matched) > 1:
            return JSONResponse({
                "query": user_query,
                "clarification": True,
                "message": f"Multiple students found named '{name}'. Please select the correct one.",
                "choices": [
                    {
                        "id": row["id"],
                        "programme": row.get("programme", "Unknown"),
                        "cohort": row.get("cohort", "Unknown")
                    } for row in matched
                ]
            })

        # ✅ One match: inject ID into query string before calling DeepSeek
        resolved_id = matched[0]["id"]
        processed_query = re.sub(name, str(resolved_id), processed_query, flags=re.IGNORECASE)

    for retry in range(10):
        try:
            if name and retry > 0 and re.search(rf"\b{name}\b", processed_query):
                resolved_id = resolve_name_to_id(name)
                if resolved_id:
                    processed_query = re.sub(name, str(resolved_id), processed_query, flags=re.IGNORECASE)

            cql = generate_cql_from_query(processed_query)

            if ";" in cql and cql.count(";") > 1:
                raise ValueError("Multiple CQL statements detected")
            cql = re.sub(r"\bFROMM\b", "FROM", cql, flags=re.IGNORECASE)
            cql = re.sub(r"\bSELECTT\b", "SELECT", cql, flags=re.IGNORECASE)

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

            if "WHERE" in cql.upper() and "ALLOW FILTERING" not in cql.upper():
                cql += " ALLOW FILTERING"

            rows = session.execute(cql)
            result = [clean_row(row) for row in rows]
            result = [dict(t) for t in {tuple(sorted(d.items())) for d in result}]  # Deduplicate

            if result and isinstance(result[0], dict) and "financialaid" in result[0]:
                all_values = []
                for row in result:
                    raw = row["financialaid"]
                    all_values.extend([x.strip() for x in raw.split(",") if x.strip()])
                result = [{"financialaid": val} for val in sorted(set(all_values))]

            return JSONResponse(
                attach_llm_verification(user_query, result, processed_query, cql)
            )

        except Exception as e:
            if retry == 9:
                return JSONResponse({"error": str(e)}, status_code=500)
