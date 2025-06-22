import spacy
import re
import json
import pandas as pd
import requests
from fuzzywuzzy import fuzz
from collections import defaultdict

# Load spaCy model (not used in LLM mode, but kept for fallback/future)
nlp = spacy.load("en_core_web_lg")

# Load student & subject data for fuzzy matching (if needed)
students_df = pd.read_csv("data/students.csv")
subjects_df = pd.read_csv("data/subjects.csv")

all_names = students_df["name"].dropna().unique().tolist()
all_programmes = students_df["programme"].dropna().unique().tolist()
all_subject_names = subjects_df["subjectname"].dropna().unique().tolist()

# 🔧 Optional: Fuzzy match helper (not used in LLM mode)
def fuzzy_match(text, choices, threshold=80):
    best_match = ""
    best_score = 0
    for choice in choices:
        score = fuzz.partial_ratio(text.lower(), choice.lower())
        if score > best_score:
            best_match = choice
            best_score = score
    return best_match if best_score >= threshold else None

# ✅ LLM fallback using LM Studio (DeepSeek)
def fallback_to_deepseek(query: str, max_retries=2):
    prompt = f"""
        You are a university AI assistant.

        Your job is to convert a user query into structured JSON for processing.

        Use "show_students" if the query is about listing students based on CGPA, programme, gender, or race.
        Use "count_failed_subjects" only if the user explicitly asks for how many subjects a student has failed.

        ✅ The output must be:
        - A JSON array of one or more objects
        - Each object must contain:
            - "intent": one of the following:
            ["predict_honors", "explain_prediction", "show_students", "list_weak_subjects", "list_strong_subjects", "count_failed_subjects", "get_subject_grades", "get_attendance_summary", "list_subjects_by_semester", "get_student_profile", "compare_students"]
            - "filters": a dictionary with keys such as:

                "id", "student_id", "name", "gender", "race", "country", "programme", "programmecode",
                "year", "sem", "broadsheetyear", "status", "awardclassification",
                "subjectname", "subjectcode",
                "cgpa_condition", "fail_rate_condition", "avg_grade_score_condition", "num_failed_condition",
                "scholarship", "financialaid"

        ❌ DO NOT explain or describe the logic.
        ❌ DO NOT use markdown, bullet points, <think>, or natural language.
        ❌ DO NOT output anything except the JSON array.

        ⚠️ Your response MUST start with a `[` character.

        ---

        🧪 Example Input:
        "Show Diana Brown’s profile and list any weak subjects she has."

        🧾 Example Output:
        [
        {{
            "intent": "get_student_profile",
            "filters": {{
            "name": "Diana Brown"
            }}
        }},
        {{
            "intent": "list_weak_subjects",
            "filters": {{
            "name": "Diana Brown"
            }}
        }}
        ]

        Now do the same for:

        "{query}"
        """

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                "http://127.0.0.1:1234/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "deepseek/deepseek-r1-0528-qwen3-8b",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1024,
                }
            )

            if response.ok:
                content = response.json()["choices"][0]["message"]["content"]
                print(f"🤖 Raw LLM response (attempt {attempt}):", repr(content))

                # Strip <think> or markdown
                cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

                match = re.search(r'\[.*\]', cleaned, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))

                    for item in parsed:
                        filters = item.get("filters", {})

                        # 🧼 Clean up any escaped quotes like '>=\"3.5\"'
                        for k, v in filters.items():
                            if isinstance(v, str):
                                filters[k] = v.replace('\\"', '').replace('"', '').strip()

                        if "student_id" in filters:
                            filters["id"] = filters.pop("student_id")

                        if "subjectname" in filters:
                            filters["subjectname"] = filters["subjectname"].replace(" ", "")

                        if "student_id" in filters:
                            filters["id"] = filters.pop("student_id")
                        if "subjectname" in filters:
                            filters["subjectname"] = filters["subjectname"].replace(" ", "")

                    return parsed

                print("⚠️ No valid JSON block found. Retrying...")

            else:
                print("❌ LLM request failed:", response.status_code, response.text)

        except Exception as e:
            print(f"❌ Error during DeepSeek fallback attempt {attempt}:", e)

    print("❌ All retry attempts failed.")
    return [{"intent": "unknown", "filters": {}}]

# ✅ Main function — always use LLM
def parse_query(query: str):
    print("🤖 [LLM MODE] Skipping spaCy/fuzzy and using DeepSeek only...")
    return fallback_to_deepseek(query)

