from fuzzywuzzy import fuzz
import re
import os
import json
from backend.constants.schema_columns import STUDENT_COLUMNS, SUBJECT_COLUMNS

# Load correct values from JSON file
json_path = os.path.join(os.path.dirname(__file__), "unique_values_fuzzy.json")
with open(json_path, "r", encoding="utf-8") as f:
    correctable_fields = json.load(f)

ALL_COLUMNS = set(SUBJECT_COLUMNS + STUDENT_COLUMNS)

def normalize_text(text: str) -> str:
    """Lowercase and remove non-alphanumeric chars for better fuzzy matching."""
    return re.sub(r'[^a-zA-Z0-9]', '', text.lower())

def correct_value(input_val: str, field_values: list, field_name: str = "", threshold: int = 70):
    """
    Fuzzy-correct a single input string against a list of valid values.
    Allows a lower threshold for specific fields like 'programme'.
    Returns None if no good match is found.
    """
    if field_name == "programme":
        threshold = 60

    input_norm = normalize_text(input_val.strip())
    best_match = None
    best_score = 0

    for candidate in field_values:
        candidate_norm = normalize_text(candidate)
        score = fuzz.ratio(input_norm, candidate_norm)

        if candidate.strip().upper() == "PROGRAMMING PRINCIPLES":
            score -= 10  # Penalize bad value

        if score > best_score:
            best_match = candidate
            best_score = score

    if best_score >= threshold:
        print(f"✅ Fuzzy match for field '{field_name}': '{input_val}' → '{best_match}' (score: {best_score})")
        return best_match
    else:
        print(f"⚠️ No good match for '{input_val}' in field '{field_name}'. Best score: {best_score}. Skipping.")
        return None

def patch_fuzzy_values(cql: str) -> str:
    """
    Patch all known fields in a CQL query by fuzzy matching literal values
    to their canonical forms from correctable_fields.
    """
    # ✅ Fix possible LLM typos in field names inside raw CQL
    cql = cql.replace("suubjectname", "subjectname")  # Add more if needed

    for field, valid_values in correctable_fields.items():
        # ✅ Fix possible typo keys from JSON or runtime mistake
        field = field.strip().lower().replace("suubjectname", "subjectname")

        pattern = fr"{field}\s*=\s*'([^']+)'"
        matches = re.findall(pattern, cql, re.IGNORECASE)
        for raw_input in matches:
            # ⛔ Avoid fuzzy-correcting if it looks like a column name
            if normalize_text(raw_input) in [normalize_text(c) for c in ALL_COLUMNS]:
                print(f"⛔ Skipping fuzzy match: '{raw_input}' looks like a column name")
                continue

            corrected = correct_value(raw_input, valid_values, field_name=field)
            if corrected and corrected != raw_input:
                print(f"🛠️ Replacing in CQL: {field}='{raw_input}' → '{corrected}'")
                cql = re.sub(
                    fr"({field}\s*=\s*)'{re.escape(raw_input)}'",
                    fr"\1'{corrected}'",
                    cql,
                    flags=re.IGNORECASE
                )
            elif corrected == raw_input:
                print(f"✅ Value already canonical for field '{field}': '{raw_input}'")
            elif corrected is None:
                print(f"❌ No correction applied for field '{field}': '{raw_input}'")

    return cql
