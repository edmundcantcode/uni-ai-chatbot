from database.connect_cassandra import session
from backend.utils.student_check import student_exists

def handle_get_subject_grades(filters: dict):
    if not session:
        return {"error": "Cassandra session is not active."}

    if "id" not in filters and "name" not in filters:
        return {"error": "No student ID or name provided."}

    # Resolve name to ID
    if "name" in filters and "id" not in filters:
        rows = session.execute("SELECT id FROM students WHERE name = %s ALLOW FILTERING", [filters["name"]])
        student_row = rows.one()
        if not student_row:
            return {"error": "Student not found."}
        filters["id"] = student_row.id

    if not student_exists(filters["id"]):
        return {"error": f"Student ID {filters['id']} does not exist."}

    try:
        if "subjectname" in filters:
            query = "SELECT subjectname, grade FROM subjects WHERE id = %s AND subjectname = %s ALLOW FILTERING"
            params = [int(filters["id"]), filters["subjectname"]]
        else:
            query = "SELECT subjectname, grade FROM subjects WHERE id = %s ALLOW FILTERING"
            params = [int(filters["id"])]

        rows = session.execute(query, params)
        results = [{"subject": row.subjectname, "grade": row.grade} for row in rows]

        # 🔍 Grade filter (if provided)
        if "grade_condition" in filters:
            condition = filters["grade_condition"]
            try:
                if condition.startswith("== "):
                    target = condition[3:].strip()
                    results = [r for r in results if r["grade"] == target]
                elif condition.startswith("in "):
                    values = eval(condition[3:].strip())  # safe if used internally
                    results = [r for r in results if r["grade"] in values]
            except Exception as e:
                return {"error": f"Invalid grade_condition format: {e}"}

        return {
            "student_id": filters["id"],
            "grades": results,
            "count": len(results)
        }

    except Exception as e:
        return {"error": str(e)}
