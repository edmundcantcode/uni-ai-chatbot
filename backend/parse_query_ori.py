import spacy
import re
from fuzzywuzzy import fuzz
from collections import defaultdict
import pandas as pd
import requests
import json

# Load spaCy model
nlp = spacy.load("en_core_web_lg")

# Load student data
students_df = pd.read_csv("data/students.csv")  # adjust path if needed
all_names = students_df["name"].dropna().unique().tolist()
all_programmes = students_df["programme"].dropna().unique().tolist()
subjects_df = pd.read_csv("data/subjects.csv")
all_subject_names = subjects_df["subjectname"].dropna().unique().tolist()

# Intent keywords
intent_phrases = {
    "predict_honors": [
        "graduate", "honors", "pass", "eligible", "succeed",
        "predict", "classification", "will get honors", "on track for honors"
    ],
    "explain_prediction": [
        "explain", "why", "reason", "at risk", "cause",
        "explain why", "not graduating", "at risk of failing"
    ],
    "show_students": [
        "show", "list", "display", "find", "get students",
        "who are", "filter", "all students", "students list", "show me"
    ],
    "list_weak_subjects": [
        "weak", "bad", "poor", "struggle", "weak at", "bad at", "failing subjects"
    ],
    "list_strong_subjects": [
        "strong", "good", "excellent", "aced", "best", "top subjects",
        "strong at", "good at", "excelled at", "top grades"
    ],
    "count_failed_subjects": [
        "how many fail", "failed count", "subjects failed", "number of fails",
        "how many did they fail", "total failed", "failed subjects"
    ],
    "list_subjects_by_semester": [
        "semester", "taken in", "modules for year", "subjects in year", "enrolled",
        "subjects in semester", "semester 1", "term", "subjects this semester"
    ],
    "get_attendance_summary": [
        "attendance", "present", "absent", "attendance summary",
        "missed class", "class attendance", "attendance rate"
    ],
    "get_subject_grades": [
        "grades", "subject results", "list grades", "results of", "transcript",
        "grades for", "subject marks", "exam results"
    ],
    "compare_students": [
        "compare", "who is better", "vs", "versus", "difference",
        "compare students", "comparison between", "who performs better"
    ],
    "get_student_profile": [
        "profile", "summary", "student info", "cgpa", "programme", "details",
        "student background", "overview", "academic info"
    ],
    "unknown": []
}
# 🔧 Fix: similarity logic
def detect_intent_semantically(doc):
    intent_scores = {intent: 0.0 for intent in intent_phrases}

    for token in doc:
        if token.is_stop or token.is_punct or token.like_num:
            continue  # ignore meaningless words like "is", "?", "204379"

        for intent, keywords in intent_phrases.items():
            for word in keywords:
                try:
                    similarity = nlp(word)[0].similarity(token)
                    if similarity > 0.7:
                        intent_scores[intent] += similarity
                except:
                    continue

    best_intent = max(intent_scores, key=intent_scores.get)
    if intent_scores[best_intent] > 0:
        print("🧠 Best intent match:", best_intent, "| Score:", intent_scores[best_intent])
        return best_intent
    return "unknown"

# 🔧 Add: fuzzy match helper
def fuzzy_match(text, choices, threshold=80):
    best_match = ""
    best_score = 0
    for choice in choices:
        score = fuzz.partial_ratio(text.lower(), choice.lower())
        if score > best_score:
            best_match = choice
            best_score = score
    return best_match if best_score >= threshold else None

# ✅ Extract filters
def extract_filters(query: str):
    filters = defaultdict(str)
    q = query.lower()

    # Gender
    if "female" in q:
        filters["gender"] = "Female"
    if "male" in q:
        filters["gender"] = "Male"

    # Race
    for race in ["chinese", "malay", "indian"]:
        if race in q:
            filters["race"] = race.upper()

    # Country
    if "international" in q:
        filters["country"] = "INTERNATIONAL"
    elif "local" in q or "malaysia" in q:
        filters["country"] = "MALAYSIA"

    # ID
    id_match = re.search(r"\b\d{6,8}\b", q)
    if id_match:
        filters["id"] = id_match.group()

    # CGPA condition
    cgpa_match = re.search(r"cgpa\s*(>|<|=|>=|<=)?\s*([0-4]\.\d+)", q)
    if cgpa_match:
        op = cgpa_match.group(1) or "="
        value = cgpa_match.group(2)
        filters["cgpa_condition"] = f"{op}{value}"

    # Name fuzzy match
    for word in q.split():
        match = fuzzy_match(word, all_names)
        if match:
            filters["name"] = match
            break

    # Programme fuzzy match
    prog_match = fuzzy_match(query, all_programmes)
    if prog_match:
        filters["programme"] = prog_match

    # ✅ Subject name fuzzy match
    subject_match = fuzzy_match(query, all_subject_names)
    if subject_match:
        filters["subjectname"] = subject_match

    return dict(filters)


# ✅ Fallback to DeepSeek
DEEPSEEK_API_URL = "http://localhost:1234/deepseek"

def fallback_to_deepseek(query: str):
    try:
        prompt = f"""
You are a university AI assistant.

You must convert the query below into structured JSON.  
Do NOT explain your reasoning.  
Do NOT use <think>, markdown, or code blocks.  
Respond with **ONLY valid JSON**, directly.

Format:
[
  {{
    "intent": one of ["predict_honors", "explain_prediction", "show_students", "list_weak_subjects", "list_strong_subjects", "count_failed_subjects", "get_subject_grades", "get_attendance_summary", "list_subjects_by_semester", "get_student_profile", "compare_students"],
    "filters": {{
      "id": "optional numeric string",
      "name": "optional full name",
      "subjectname": "optional subject name",
      "programme": "optional programme name"
    }}
  }}
]

Query: "{query}"
"""

        response = requests.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": "deepseek/deepseek-r1-0528-qwen3-8b",  # exact model from your screenshot
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 512
            }
        )

        if response.ok:
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            print("🤖 Raw LLM response:", content)

            return json.loads(content.strip())  # Converts string → list of dicts
        else:
            print("❌ LLM response not OK:", response.status_code, response.text)

    except Exception as e:
        print("❌ DeepSeek fallback failed:", e)

    return [{"intent": "unknown", "filters": {}}]


# ✅ Main parser
# def parse_query(query: str):
#     doc = nlp(query)
#     intent = detect_intent_semantically(doc)

#     if intent != "unknown":
#         filters = extract_filters(query)
#         return [{"intent": intent, "filters": filters}]
#     else:
#         print("🤖 Falling back to DeepSeek...")
#         return fallback_to_deepseek(query)


def parse_query(query: str):
    print("🤖 [LLM MODE] Skipping spaCy and using DeepSeek/LM Studio only...")
    return fallback_to_deepseek(query)