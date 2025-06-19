from database.connect_cassandra import session
from backend.utils.student_check import student_exists

# Define weak grades here or import from constants.py
WEAK_GRADES = {"C", "D", "F", "F*"}

def handle_list_weak_subjects(filters: dict):
    if not session:
        return {"error": "Cassandra session is not active."}

    if "id" not in filters and "name" not in filters:
        return {"error": "No student ID or name provided."}

    # Resolve name to ID
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
        weak_subjects = [
            {"subject": row.subjectname, "grade": row.grade}
            for row in rows if row.grade in WEAK_GRADES
        ]

        return {
            "student_id": filters["id"],
            "weak_subjects": weak_subjects,
            "count": len(weak_subjects)
        }
    except Exception as e:
        return {"error": str(e)}
