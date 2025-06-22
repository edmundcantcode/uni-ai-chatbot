from database.connect_cassandra import session
from backend.utils.student_check import student_exists

def classify_award_logic(filters: dict):
    if not session:
        return {"error": "❌ Cassandra session is not active."}

    if "id" not in filters and "name" not in filters:
        return {"error": "❌ Missing student ID or name."}

    # 🔁 Get ID by name if needed
    if "id" not in filters and "name" in filters:
        rows = session.execute("SELECT id FROM students WHERE name = %s ALLOW FILTERING", [filters["name"]])
        row = rows.one()
        if not row:
            return {"error": f"❌ Student {filters['name']} not found."}
        filters["id"] = row.id

    student_id = int(filters["id"])

    if not student_exists(student_id):
        return {"error": f"❌ Student ID {student_id} does not exist."}

    # 🎯 Get CGPA
    query = "SELECT overallcgpa FROM students WHERE id = %s"
    row = session.execute(query, [student_id]).one()

    if not row:
        return {"error": f"❌ Could not retrieve data for student {student_id}."}

    cgpa = row.overallcgpa

    # 🧠 Classify
    if cgpa >= 3.5:
        classification = "Class I"
    elif cgpa >= 3.0:
        classification = "Class II (I)"
    elif cgpa >= 2.5:
        classification = "Class II (II)"
    elif cgpa >= 2.0:
        classification = "Class III"
    else:
        classification = "Fail"

    return {
        "student_id": student_id,
        "overallcgpa": cgpa,
        "classification": classification,
        "criteria": {
            "Class I": "3.50 – 4.00",
            "Class II (I)": "3.00 – 3.49",
            "Class II (II)": "2.50 – 2.99",
            "Class III": "2.00 – 2.49",
            "Fail": "< 2.00"
        }
    }
