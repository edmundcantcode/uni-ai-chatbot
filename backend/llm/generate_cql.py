import requests
import re
from backend.database.connect_cassandra import session
from backend.llm.connect_deepseek import LLAMA3_API_URL
from backend.utils.fuzzy_matcher import patch_fuzzy_values
from backend.constants.schema_columns import STUDENT_COLUMNS, SUBJECT_COLUMNS

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

Input: list subject codes for Programming Principles
Output: SELECT subjectcode FROM subjects WHERE subjectname = 'ProgrammingPrinciples';

Input: list students in Bachelor of Software Engineering (Hons)
Output: SELECT id, name FROM students WHERE programme = 'Bachelor of Software Engineering (Hons)';

Input: show IDs of students in Programming Principles
Output: SELECT id FROM subjects WHERE subjectname = 'ProgrammingPrinciples';
"""

def build_prompt(user_query: str) -> str:
    return (
        f"You are given the following Cassandra tables:\n\n"
        f"Table: students\nColumns: {', '.join(STUDENT_COLUMNS)}\n\n"
        f"Table: subjects\nColumns: {', '.join(SUBJECT_COLUMNS)}\n\n"
        f"{EXAMPLES.strip()}\n\n"
        f"Now, generate the correct CQL query for this natural language input:\n"
        f"\"{user_query}\"\n\n"
        f"Only return the CQL query. Do NOT explain. Do NOT include markdown.\n"
        f"Cassandra does NOT support subqueries or JOINs.\n"
        f"Use 'subjectname' for course subjects like Programming Principles, Artificial Intelligence, etc.\n"
        f"Use 'programme' only for full degree names like 'Bachelor of Software Engineering (Hons)'.\n"
        f"Never confuse subject names with programme names.\n"
        f"If the input mentions a specific course or module like 'Programming Principles', it must be matched with 'subjectname', not 'programme'.\n"
        f"Never include 'IS NOT NULL' in your queries.\n"
        f"Avoid SELECT * unless querying subjects.\n"
        f"Do not quote numeric values like year or cohort.\n"
        f"Only include columns from STUDENT COLUMNS and SUBJECT COLUMNS that the query specifies.\n"
        f"Strictly never use * unless stated otherwise."
        f"\n\nHere are what the SUBJECT columns mean:\n"
        f"- attendancepercentage: Percentage of attendance\n"
        f"- courseworkpercentage: Marks from assignments, projects, or lab work\n"
        f"- exampercentage: Marks from final exams\n"
        f"- overallpercentage: Total final mark from all components\n"
    )

def generate_cql_from_query(user_query: str, retries=10):
    prompt = build_prompt(user_query)
    print("Using LLaMA-3 to generate CQL...")
    print(f"Prompt length: {len(prompt)} characters")

    last_error = None

    for attempt in range(1, retries + 1):
        try:
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
                                "Cassandra does NOT support subqueries or JOINs. "
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

            cql = raw.strip().split("```")[-1].strip().rstrip(";")

            if not cql.lower().startswith("select") or any(op in cql.lower() for op in ["drop", "delete", "join"]):
                raise ValueError("Unsafe or invalid CQL returned.")

            cql = patch_fuzzy_values(cql)

            if "programme = 'Programming Principles'" in cql or "programme = 'programming principles'" in cql:
                print("❌ Detected invalid mapping of subjectname to programme. Retrying...")
                raise ValueError("Invalid field association: subjectname used as programme")

            if "Programming Principles" in cql:
                print("❌ Detected bad value 'Programming Principles' still in CQL. Forcing retry...")
                raise ValueError("Bad fuzzy match: 'Programming Principles' was not corrected")

            print("🧠 Fuzzy-matched CQL:", cql)
            return cql

        except Exception as e:
            print(f"❌ Attempt {attempt} failed with error: {e}")
            last_error = e

    raise RuntimeError(f"Failed to generate a valid CQL query after {retries} attempts. Last error: {last_error}")
