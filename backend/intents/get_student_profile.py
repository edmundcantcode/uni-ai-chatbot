from database.connect_cassandra import session
from backend.utils.student_check import student_exists

def handle_get_student_profile(filters: dict):
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
        # Get student profile info
        row = session.execute("SELECT name, programme, overallcgpa, awardclassification FROM students WHERE id = %s", [int(filters["id"])]).one()
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
