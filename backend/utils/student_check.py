from database.connect_cassandra import session

def student_exists(student_id):
    if not session:
        return False

    try:
        rows = session.execute("SELECT id FROM students WHERE id = %s", [int(student_id)])
        return rows.one() is not None
    except Exception as e:
        print("Error during student_exists check:", e)
        return False
