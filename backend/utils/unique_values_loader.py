import json
import os

def get_all_non_name_values():
    file_path = os.path.join(os.path.dirname(__file__), "unique_values_prompt.json")
    with open(file_path, "r") as f:
        data = json.load(f)
    all_values = set()
    for values in data.values():
        for val in values:
            if not isinstance(val, str):
                print(f"⚠️ Non-string value skipped in unique values: {val} ({type(val)})")
            else:
                all_values.add(val)
    return all_values