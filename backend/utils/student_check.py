from fuzzywuzzy import fuzz
from backend.database.connect_cassandra import session

# 📥 Load all names + IDs
def get_all_students():
    rows = session.execute("SELECT id, name, programme, cohort FROM students")
    return [dict(row._asdict()) for row in rows]

# 🎯 Fuzzy match a name to one best ID
def resolve_name_to_id(name_query: str, threshold=85):
    students = get_all_students()
    best_match = None
    best_score = 0

    for student in students:
        score = fuzz.partial_ratio(name_query.lower(), student["name"].lower())
        if score > best_score:
            best_match = student
            best_score = score

    return best_match["id"] if best_score >= threshold else None

# 🔁 Return all exact matches by name
def resolve_all_ids_by_name(name: str):
    rows = session.execute(f"SELECT id, name, programme, cohort FROM students WHERE name = '{name}' ALLOW FILTERING")
    matched = [row._asdict() for row in rows]
    print("🧠 Matched IDs:", matched)
    return matched

