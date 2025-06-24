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

def extract_name_if_present(text: str):
    match = re.search(r"\b([A-Z][a-z]+\s[A-Z][a-z]+)\b", text)
    return match.group(1) if match else None

def deep_convert(obj):
    if isinstance(obj, dict):
        return {str(deep_convert(k)): deep_convert(v) for k, v in obj.items()}
    elif isinstance(obj, (SortedSet, OrderedMapSerializedKey, set, frozenset)):
        return [deep_convert(item) for item in obj]
    elif isinstance(obj, list):
        return [deep_convert(item) for item in obj]
    elif hasattr(obj, "_asdict"):
        return deep_convert(obj._asdict())
    elif hasattr(obj, "__dict"):
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

@router.post("/chatbot")
async def chatbot_endpoint(payload: QueryRequest):
    try:
        user_query = payload.query.strip()
        processed_query = user_query

        name = extract_name_if_present(user_query)
        if name:
            resolved_id = resolve_name_to_id(name)
            if resolved_id:
                processed_query = user_query.replace(name, str(resolved_id))

        for retry in range(10):
            try:
                cql, explanation = generate_cql_from_query(processed_query)
                if "ProgrammING PRINCIPLES" in cql or "subjectname = 'Programming Principles'" in cql:
                    print("❌ Detected bad 'Programming Principles' logic, retrying...")
                    continue
                break
            except RuntimeError as e:
                if retry == 9:
                    return JSONResponse({"error": "❌ Failed to generate CQL after multiple retries.", "details": str(e)}, status_code=500)

        print("▶️ Final CQL to execute:", cql)

        subquery_pattern = r"id\s*(=|IN)\s*\(SELECT id FROM students WHERE name\s*=\s*'([^']+)'"
        matches = re.findall(subquery_pattern, cql, re.IGNORECASE)
        for match in matches:
            student_name = match[1]
            id_result = session.execute(f"SELECT id FROM students WHERE name = '{student_name}' ALLOW FILTERING").one()
            if id_result:
                student_id = id_result.id
                cql = re.sub(subquery_pattern, f"id = {student_id}", cql, flags=re.IGNORECASE)
                print(f"🔁 Patched subquery CQL with ID {student_id}: {cql}")
            else:
                return JSONResponse({"error": f"❌ Student '{student_name}' not found."}, status_code=404)

        statements = [stmt.strip() for stmt in cql.split(";") if stmt.strip()]
        if len(statements) > 1:
            first_result = session.execute(statements[0] + " ALLOW FILTERING")
            first_row = first_result.one()
            if not first_row:
                return JSONResponse({"error": "No data found in first query."}, status_code=404)
            student_id = first_row.id

            patched_statements = []
            for stmt in statements[1:]:
                patched_stmt = re.sub(r"id\s*(=|IN)\s*\(.*?\)", f"id = {student_id}", stmt)
                patched_statements.append(patched_stmt)

            results = []
            for stmt in patched_statements:
                res = session.execute(stmt + " ALLOW FILTERING")
                results.append([clean_row(row) for row in res])

            return JSONResponse({"query": user_query, "processed_query": processed_query, "cql": cql, "results": results, "explanation": explanation})

        if "IN (SELECT" in cql.upper() or ("IN(" in cql.upper() and "SELECT" in cql.upper()):
            print("⚠️ Detected invalid subquery in CQL. Attempting manual split...")
            match = re.search(r"subjectname\s*=\s*'([^']+)'", cql, re.IGNORECASE)
            if match:
                subjectname = match.group(1)
                subject_query = f"SELECT id FROM subjects WHERE subjectname = '{subjectname}' ALLOW FILTERING;"
                subject_ids = session.execute(subject_query)
                id_list = [str(row.id) for row in subject_ids]
                if not id_list:
                    return JSONResponse({"error": "No students found for that subject."}, status_code=404)
                cql = f"SELECT id, name FROM students WHERE id IN ({', '.join(id_list)});"
                print("🧠 Rewritten CQL:", cql)

        if "programmecode = (SELECT programmecode FROM subjects" in cql:
            print("⚠️ Detected subquery on programmecode. Rewriting manually...")
            subject_match = re.search(r"subjectname\s*=\s*'([^']+)'", cql, re.IGNORECASE)
            grade_match = re.search(r"grade\s*=\s*'([^']+)'", cql, re.IGNORECASE)
            if subject_match:
                subjectname = subject_match.group(1)
                grade_clause = f" AND grade = '{grade_match.group(1)}'" if grade_match else ""
                subject_query = f"SELECT programmecode FROM subjects WHERE subjectname = '{subjectname}'{grade_clause} ALLOW FILTERING;"
                result = session.execute(subject_query).one()
                if not result:
                    return JSONResponse({"error": f"No programmecode found for subject '{subjectname}'"}, status_code=404)
                pc = result.programmecode
                cql = f"SELECT id, name FROM students WHERE programmecode = '{pc}'"
                print(f"🧠 Rewritten CQL using programmecode '{pc}': {cql}")

        if "WHERE" in cql.upper() and "ALLOW FILTERING" not in cql.upper():
            cql += " ALLOW FILTERING"

        rows = session.execute(cql)
        result = [clean_row(row) for row in rows]

        return JSONResponse({
            "query": user_query,
            "processed_query": processed_query,
            "cql": cql,
            "result": result,
            "explanation": explanation
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
