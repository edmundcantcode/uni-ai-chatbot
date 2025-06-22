from database.connect_cassandra import session
from backend.utils.student_check import student_exists

def check_honors_class(filters: dict):
    if not session:
        return {"error": "❌ Cassandra session is not active."}

    if "id" not in filters and "name" not in filters:
        return {"error": "❌ Missing student ID or name."}

    # 🔄 Resolve student ID if only name is given
    if "id" not in filters:
        rows = session.execute("SELECT id FROM students WHERE name = %s ALLOW FILTERING", [filters["name"]])
        row = rows.one()
        if not row:
            return {"error": f"❌ Student '{filters['name']}' not found."}
        filters["id"] = row.id

    student_id = int(filters["id"])

    if not student_exists(student_id):
        return {"error": f"❌ Student ID {student_id} does not exist."}

    # 🎓 Fetch CGPA
    row = session.execute("SELECT overallcgpa FROM students WHERE id = %s", [student_id]).one()
    if not row:
        return {"error": f"❌ No data found for student ID {student_id}."}

    cgpa = row.overallcgpa

    # 🧠 Determine classification
    if cgpa >= 3.5:
        honors_class = "Class I"
    elif cgpa >= 3.0:
        honors_class = "Class II (I)"
    elif cgpa >= 2.5:
        honors_class = "Class II (II)"
    elif cgpa >= 2.0:
        honors_class = "Class III"
    else:
        honors_class = "No Honors"

    return {
        "student_id": student_id,
        "cgpa": cgpa,
        "honors_class": honors_class,
        "criteria": {
            "Class I": "3.50 – 4.00",
            "Class II (I)": "3.00 – 3.49",
            "Class II (II)": "2.50 – 2.99",
            "Class III": "2.00 – 2.49",
            "No Honors": "< 2.00"
        }
    }
