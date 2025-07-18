import requests
import re
import os
import json
from backend.database.connect_cassandra import session
from backend.llm.connect_llm import LLAMA3_API_URL
from backend.utils.fuzzy_matcher import patch_fuzzy_values
from backend.constants.schema_columns import STUDENT_COLUMNS, SUBJECT_COLUMNS

# Load real unique values for value hinting
UNIQUE_VALUES_PATH = os.path.join(os.path.dirname(__file__), "..", "utils", "unique_values_prompt.json")
with open(UNIQUE_VALUES_PATH, "r") as f:
    UNIQUE_VALUES = json.load(f)

EXAMPLES = """
Input: show students who are female
Output: SELECT id, name, gender FROM students WHERE gender = 'Female';

Input: get CGPA for Diana Davis
Output: SELECT overallcgpa FROM students WHERE name = 'Diana Davis';

Input: show subjects taken by Bob Johnson
Output: SELECT * FROM subjects WHERE id = 9897587;

Input: list all subjects
Output: SELECT subjectname, subjectcode FROM subjects ALLOW FILTERING;

Input: show all available subjects
Output: SELECT subjectname, subjectcode FROM subjects ALLOW FILTERING;

Input: show all available subjects
Output: SELECT DISTINCT subjectname, subjectcode FROM subjects;

Input: what subjects are offered
Output: SELECT DISTINCT subjectname FROM subjects;

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
    # Add real example values for categorical fields
    value_guidance = "\nHere are example valid values:\n"
    for key, values in UNIQUE_VALUES.items():
        if not values:
            continue
        examples = ", ".join(repr(v) for v in values[:5])
        value_guidance += f"- {key}: {examples}\n"

    return (
        f"You are given the following Cassandra tables:\n\n"
        f"Table: students\nColumns: {', '.join(STUDENT_COLUMNS)}\n"
        f"Table: subjects\nColumns: {', '.join(SUBJECT_COLUMNS)}\n\n"
        f"{value_guidance}\n"
        f"Here is what the STUDENT columns mean:\n"
        f"- id: Unique student identifier (e.g., 9897587)\n"
        f"- programme: Full name of the degree programme (e.g., 'BSc (Hons) in Computer Science')\n"
        f"- awardclassification: Final award class (e.g., 'Class I')\n"
        f"- broadsheetyear: Year of graduation (e.g., 2021.0)\n"
        f"- cavg: Current average mark (e.g., 73.24)\n"
        f"- cohort: Student intake code or batch (e.g., 201803.0)\n"
        f"- country: Student's country of origin (e.g., 'MALAYSIA')\n"
        f"- financialaid: Scholarship or aid the student received (e.g., 'JEFFREY CHEAH ACE SCHOLARSHIP')\n"
        f"- gender: Gender of the student (e.g., 'Male')\n"
        f"- graduated: Whether the student has graduated (e.g., True)\n"
        f"- ic: Identity card number (e.g., 3145431)\n"
        f"- name: Full name of the student (e.g., 'Bob Johnson')\n"
        f"- overallcavg: Cumulative average (e.g., 73.24)\n"
        f"- overallcgpa: Cumulative GPA (e.g., 0.0)\n"
        f"- programmecode: Code for the programme (e.g., '481BCS')\n"
        f"- qualifications: Entry qualifications (e.g., '[{{qualificationCode=FST, ...}}]')\n"
        f"- race: Ethnicity (e.g., 'CHINESE')\n"
        f"- sem: Current semester number (e.g., 9)\n"
        f"- sponsorname: Organization funding the student directly (e.g., 'PETROLIAM NASIONAL BERHAD'). Usually a single entity.\n"
        f"- status: Enrolment status (e.g., 'Active, 'Completed','Defer','Excluded','Finished','Not Enrol','Transfer Out','Withdraw')\n"
        f"- subjects: List of subject records\n"
        f"- year: Graduation year (e.g., 2021.0)\n"
        f"- yearoneaverage: Year 1 average mark (e.g., 75.78)\n"
        f"- yearonecgpa: Year 1 CGPA (e.g., 3.25)\n\n"
        f"Here is what the SUBJECT columns mean:\n"
        f"- id: Student ID (foreign key)\n"
        f"- programmecode: Programme code (e.g., '481BCS')\n"
        f"- subjectcode: Subject code (e.g., 'BIS2212(MU32422)')\n"
        f"- subjectname: Subject title (e.g., 'Programming Principles')\n"
        f"- examyear: Exam year (e.g., 2022)\n"
        f"- exammonth: Exam month (e.g., 3)\n"
        f"- status: Completion status (e.g., 'Passed')\n"
        f"- attendancepercentage: Attendance % (e.g., 85.0)\n"
        f"- courseworkpercentage: Coursework % (e.g., 40.0)\n"
        f"- exampercentage: Exam % (e.g., 60.0)\n"
        f"- grade: Final grade (e.g., 'A')\n"
        f"- overallpercentage: Total mark (e.g., 90.0)\n\n"
        f"{EXAMPLES.strip()}\n\n"
        f"Now, generate the correct CQL query for this natural language input:\n"
        f"\"{user_query}\"\n\n"
        f"Only return the CQL query. Do NOT explain. Do NOT include markdown.\n"
        f"Cassandra does NOT support subqueries or JOINs.\n"
        f"Use 'subjectname' for module/course names like Programming Principles.\n"
        f"Use 'programme' only for degree names like Bachelor of IT.\n"
        f"Never confuse subject names with programme names.\n"
        f"Never quote numeric values like year or cohort.\n"
        f"Avoid SELECT * unless querying full subjects.\n"
        f"Strictly never use subqueries or JOINs."
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
                                "Never use subqueries. Only return the correct query string."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ]
                }
            )

            if response.status_code != 200:
                raise RuntimeError(f"LLM error {response.status_code}: {response.text}")

            raw = response.json()["choices"][0]["message"]["content"]
            print("Raw LLM output:", repr(raw))

            cql = raw.strip().split("```")[-1].strip().rstrip(";")

            if not cql.lower().startswith("select") or any(bad in cql.lower() for bad in ["drop", "delete", "join"]):
                raise ValueError("Unsafe or invalid CQL")

            cql = patch_fuzzy_values(cql)

            if "programme = 'Programming Principles'" in cql.lower():
                print("❌ Invalid mapping of subject to programme. Retrying...")
                raise ValueError("Misuse of subjectname vs programme")

            print("🧠 Fuzzy-matched CQL:", cql)
            return cql

        except Exception as e:
            print(f"❌ Attempt {attempt} failed: {e}")
            last_error = e

    raise RuntimeError(f"Failed after {retries} attempts. Last error: {last_error}")
