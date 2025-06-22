from database.connect_cassandra import session
from backend.utils.student_check import student_exists

def handle_get_student_profile(filters: dict):
    if not session:
        return {"error": "Cassandra session is not active."}

    if "id" not in filters and "name" not in filters:
        return {"error": "No student ID or name provided."}

    # 🎯 If only name is provided, find all matching names
    if "name" in filters and "id" not in filters:
        rows = session.execute(
            "SELECT id, name, programme, sem FROM students WHERE name = %s ALLOW FILTERING",
            [filters["name"]]
        )
        matches = [dict(row._asdict()) for row in rows]

        if not matches:
            return {"error": f"No student found with name '{filters['name']}'."}

        if len(matches) > 1:
            return {
                "error": f"⚠️ Multiple students found with name '{filters['name']}'. Please specify ID or programme.",
                "candidates": [
                    {"id": s["id"], "programme": s.get("programme", ""), "sem": s.get("sem", "")}
                    for s in matches
                ]
            }

        # ✅ Only one match, use that ID
        filters["id"] = matches[0]["id"]

    # ❓ Double check if student exists
    if not student_exists(filters["id"]):
        return {"error": f"Student ID {filters['id']} does not exist."}

    try:
        row = session.execute(
            "SELECT name, programme, overallcgpa, awardclassification FROM students WHERE id = %s",
            [int(filters["id"])]
        ).one()

        if not row:
            return {"error": "Student record not found."}

        return {
            "student_id": filters["id"],
            "name": row.name,
            "programme": row.programme,
            "cgpa": row.overallcgpa,
            "awardclassification": row.awardclassification or "Not classified"
        }

    except Exception as e:
        return {"error": str(e)}
