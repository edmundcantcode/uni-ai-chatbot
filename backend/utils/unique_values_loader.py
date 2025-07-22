import json
import os

def simplify_unique_value_keys():
    file_path = os.path.join(os.path.dirname(__file__), "unique_values_prompt.json")

    # Load the original file
    with open(file_path, "r") as f:
        data = json.load(f)

    # Build new dict with simplified keys
    simplified_data = {}
    for key, values in data.items():
        simplified_key = key.split(".")[-1]  # e.g., "subjects.subjectname" → "subjectname"
        simplified_data[simplified_key] = values

    # Overwrite the file with the new structure
    with open(file_path, "w") as f:
        json.dump(simplified_data, f, indent=2)

    print("✅ unique_values_prompt.json keys updated successfully.")

if __name__ == "__main__":
    simplify_unique_value_keys()