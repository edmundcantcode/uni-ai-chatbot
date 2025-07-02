
import json
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database.connect_cassandra import session

# Fields to extract from students and subjects tables
fields = {
    "students": ["country", "gender", "race", "programme", "awardclassification"],
    "subjects": ["subjectname"]
}

def get_distinct_values(table: str, column: str):
    query = f"SELECT {column} FROM {table}"
    try:
        rows = session.execute(query)
        return sorted(set(row[0] for row in rows if row[0] is not None))
    except Exception as e:
        print(f"❌ Failed to fetch {column} from {table}: {e}")
        return []

def extract_all_values():
    data = {}
    for table, cols in fields.items():
        for col in cols:
            print(f"🔍 Extracting: {table}.{col}")
            data[col] = get_distinct_values(table, col)

    output_path = os.path.join(os.path.dirname(__file__), "unique_values_fuzzy.json")
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
        print(f"✅ Saved to {output_path}")

if __name__ == "__main__":
    extract_all_values()
