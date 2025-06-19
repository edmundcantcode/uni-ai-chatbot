from database.connect_cassandra import session
from backend.utils.student_check import student_exists

STRONG_GRADES = {"A", "A-", "B+", "B"}

def handle_list_strong_subjects(filters: dict):
    if not session:
        return {"error": "❌ Cassandra session is not active."}

    if "id" not in filters and "name" not in filters:
        return {"error": "Please provide a student ID or name."}

    if "id" in filters:
        if not student_exists(filters["id"]):
            return {"error": f"Student ID {filters['id']} does not exist."}
    elif "name" in filters:
        rows = session.execute("SELECT id FROM students WHERE name = %s ALLOW FILTERING", [filters["name"]])
        student_row = rows.one()
        if not student_row:
            return {"error": "Student not found"}
        filters["id"] = student_row.id

    try:
        rows = session.execute("SELECT subjectname, grade FROM subjects WHERE id = %s", [int(filters["id"])])
        strong_subjects = [row.subjectname for row in rows if row.grade in STRONG_GRADES]
        return {
            "student_id": filters["id"],
            "strong_subjects": strong_subjects,
            "count": len(strong_subjects)
        }
    except Exception as e:
        return {"error": str(e)}