import pandas as pd
import numpy as np
import os

# Load data
students = pd.read_csv("data/students.csv")
subjects = pd.read_csv("data/subjects.csv")

# Label: honors = 1 if CGPA >= 3.5
students["honors"] = (students["overallcgpa"] >= 3.5).astype(int)

# Grade mapping
grade_map = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0, "P": 1.5, "EX": 3.5, "INC": 0.5, "": np.nan, None: np.nan}
subjects["grade_score"] = subjects["grade"].map(grade_map)

# Aggregate subject data
agg = subjects.groupby("id").agg({
    "subjectcode": "count",
    "grade": lambda x: sum(1 for g in x if g == "F"),
    "grade_score": "mean"
}).reset_index()

agg.columns = ["id", "num_subjects", "num_failed", "avg_grade_score"]
agg["fail_rate"] = agg["num_failed"] / agg["num_subjects"]

# Merge
merged = pd.merge(students, agg, on="id", how="left")

# Cleaned dataset
final = merged[[
    "gender", "race", "country", "programme", "year",
    "num_subjects", "num_failed", "avg_grade_score", "fail_rate", "honors"
]]

# Save
os.makedirs("data", exist_ok=True)
final.to_csv("data/merged_for_training.csv", index=False)
print("✅ Honors dataset saved.")
