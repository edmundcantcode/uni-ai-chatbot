from fuzzywuzzy import fuzz
import re
import os
import json

# ✅ Load correct values from JSON file
json_path = os.path.join(os.path.dirname(__file__), "unique_values.json")
with open(json_path, "r") as f:
    correctable_fields = json.load(f)

# ✅ Fuzzy correct a single input string
def correct_value(input_val: str, field_values: list, threshold: int = 85):
    input_val_lower = input_val.strip().lower()
    best_match = None
    best_score = 0
    for candidate in field_values:
        score = fuzz.ratio(input_val_lower, candidate.lower())
        if score > best_score:
            best_match = candidate
            best_score = score
    return best_match if best_score >= threshold else input_val  # fallback

# ✅ Patch known fields in a CQL query
def patch_fuzzy_values(cql: str) -> str:
    for field, valid_values in correctable_fields.items():
        pattern = fr"{field} = '([^']+)'"
        match = re.search(pattern, cql, re.IGNORECASE)
        if match:
            raw_input = match.group(1)
            corrected = correct_value(raw_input, valid_values)
            cql = cql.replace(match.group(0), f"{field} = '{corrected}'")
    return cql
