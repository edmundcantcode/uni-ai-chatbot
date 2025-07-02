import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.database.connect_cassandra import session

# Only include categorical/text-like fields for LLM guidance
fields = {
    "students": [
        "programme", "awardclassification", "country", "financialaid", "gender",
        "graduated", "race", "sponsorname", "status", "cohort"
    ],
    "subjects": [
        "subjectname", "subjectcode", "programmecode", "status", "grade",
        "examyear", "exammonth"
    ]
}

# Fields that often contain comma-separated compound values
split_fields = {"financialaid", "sponsorname"}

def get_distinct_values(table: str, column: str):
    query = f"SELECT {column} FROM {table} ALLOW FILTERING"
    try:
        rows = session.execute(query)
        raw_values = [row[0] for row in rows if row[0] is not None]

        if column in split_fields:
            flattened = []
            for val in raw_values:
                flattened.extend([x.strip() for x in val.split(",") if x.strip()])
            return sorted(set(flattened))
        else:
            return sorted(set(raw_values))
    except Exception as e:
        print(f"❌ Failed to fetch {column} from {table}: {e}")
        return []

def extract_all_for_llm():
    data = {}
    for table, cols in fields.items():
        for col in cols:
            print(f"🔍 Extracting for LLM: {table}.{col}")
            values = get_distinct_values(table, col)
            data[f"{table}.{col}"] = values

    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "unique_values_prompt.json"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        print(f"✅ Saved LLM-friendly unique values to: {output_path}")

if __name__ == "__main__":
    extract_all_for_llm()
