from database.connect_cassandra import session
from backend.utils.student_check import student_exists

FAILED_GRADES = {"F", "F*", "RS2"}

def handle_list_failed_subjects(filters: dict):
    if not session:
        return {"error": "Cassandra session is not active."}

    if "id" not in filters and "name" not in filters:
        return {"error": "No student ID or name provided."}

    # Resolve ID by name if needed
    if "name" in filters and "id" not in filters:
        rows = session.execute("SELECT id FROM students WHERE name = %s ALLOW FILTERING", [filters["name"]])
        student_row = rows.one()
        if not student_row:
            return {"error": "Student not found"}
        filters["id"] = student_row.id

    if not student_exists(filters["id"]):
        return {"error": f"Student ID {filters['id']} does not exist."}

    try:
        rows = session.execute("SELECT subjectname, grade FROM subjects WHERE id = %s", [int(filters["id"])])
        failed_subjects = [row.subjectname for row in rows if row.grade in FAILED_GRADES]
        return {
            "student_id": filters["id"],
            "failed_subjects": failed_subjects,
            "count": len(failed_subjects)
        }
    except Exception as e:
        return {"error": str(e)}
