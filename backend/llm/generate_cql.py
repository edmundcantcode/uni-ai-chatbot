# backend/llm/generate_cql.py

import requests
import re
from backend.database.connect_cassandra import session
from backend.llm.connect_deepseek import LLAMA3_API_URL
from backend.utils.fuzzy_matcher import patch_fuzzy_values

# ✅ Full headers from actual CSV files
STUDENT_COLUMNS = [
    "id", "programme", "awardclassification", "broadsheetyear", "cavg",
    "cohort", "country", "financialaid", "gender", "graduated", "ic", "name",
    "overallcavg", "overallcgpa", "programmecode", "qualifications", "race",
    "sem", "sponsorname", "status", "subjects", "year", "yearoneaverage", "yearonecgpa"
]

SUBJECT_COLUMNS = [
    "id", "programmecode", "subjectcode", "subjectname", "examyear",
    "exammonth", "status", "attendancepercentage", "courseworkpercentage",
    "exampercentage", "grade", "overallpercentage"
]

EXAMPLES = """
Input: show students who are female
Output: SELECT id, name, gender FROM students WHERE gender = 'Female';

Input: get CGPA for Diana Davis
Output: SELECT overallcgpa FROM students WHERE name = 'Diana Davis';

Input: show subjects taken by Bob Johnson
Output: SELECT * FROM subjects WHERE id = 9897587;

Input: get subject grades for Charlie Davis
Output: SELECT subjectname, grade FROM subjects WHERE id = 860750;

Input: list students from Sudan
Output: SELECT id, name, country FROM students WHERE country = 'SUDAN';

Input: show male students from Nigeria
Output: SELECT id, name, gender, country FROM students WHERE gender = 'Male' AND country = 'NIGERIA';
"""

# 🧠 Build the prompt
def build_prompt(user_query: str) -> str:
    return (
        f"You are given the following Cassandra tables:\n\n"
        f"Table: students\nColumns: {', '.join(STUDENT_COLUMNS)}\n"
        f"Table: subjects\nColumns: {', '.join(SUBJECT_COLUMNS)}\n\n"
        f"{EXAMPLES.strip()}\n\n"
        f"Now, generate the correct CQL query for this natural language input:\n"
        f"\"{user_query}\"\n\n"
        f"Only return the CQL query. Do NOT explain. Do NOT include markdown. Cassandra does NOT support subqueries. "
        f"Never include 'IS NOT NULL' in your queries. Avoid SELECT * unless querying the subjects table. "
        f"Always include the columns you filter by. Do not quote numeric values like year or cohort."
    )

# 🚀 Generate CQL from LLM
def generate_cql_from_query(user_query: str, retries=5):
    prompt = build_prompt(user_query)
    print("Using LLaMA-3 to generate CQL...")
    print(f"Prompt length: {len(prompt)} characters")

    for attempt in range(1, retries + 1):
        print(f"Attempt {attempt}...")
        response = requests.post(
            LLAMA3_API_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": "llama-3-8b-lexi-uncensored",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert in Cassandra CQL. "
                            "Cassandra does NOT support subqueries. "
                            "Always assume the student ID is already known and use direct values like: "
                            "SELECT * FROM subjects WHERE id = 123456. "
                            "Only return the correct final CQL query. Do NOT explain. Do NOT use markdown."
                        )
                    },
                    {"role": "user", "content": prompt}
                ]
            }
        )

        if response.status_code != 200:
            raise RuntimeError(f"DeepSeek error {response.status_code}: {response.text}")

        raw = response.json()["choices"][0]["message"]["content"]
        print("Raw LLM output:", repr(raw))

        # 🧹 Extract the CQL line
        cql = raw.strip().split("```")[-1].strip().rstrip(";")

        if not cql.lower().startswith("select") or any(op in cql.lower() for op in ["drop", "delete"]):
            print("Invalid or unsafe CQL returned. Retrying...")
            continue

        # 🧠 Apply fuzzy corrections
        patched_cql = patch_fuzzy_values(cql)

        # 🛠️ Patch string-wrapped numeric fields like year = '2022' → year = 2022
        patched_cql = re.sub(r"(year|cohort|examyear|exammonth|overallcgpa|yearonecgpa|yearoneaverage)\s*=\s*'?(\d+(\.\d+)?)'", r"\1 = \2", patched_cql)

        print("🧠 Fuzzy-matched CQL:", patched_cql)

        # 🚫 Retry if CQL is empty or unchanged nonsense
        if patched_cql.strip() == "" or "??" in patched_cql:
            print("⚠️ Empty or broken CQL returned. Retrying...")
            continue

        return patched_cql

    raise ValueError("❌ Failed to generate a valid CQL query after multiple attempts.")
