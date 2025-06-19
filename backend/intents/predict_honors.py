import joblib
import numpy as np
from database.connect_cassandra import session
from backend.utils.student_check import student_exists
import pandas as pd

# Load model and encoders
model = joblib.load("models/honors_model.pkl")
encoders = joblib.load("models/label_encoders.pkl")
feature_names = joblib.load("models/feature_names.pkl")

def predict_honors_logic(filters):
    student_id = filters.get("id")
    if not student_id:
        return {"error": "Missing student ID"}

    try:
        student_id = int(student_id)
    except ValueError:
        return {"error": f"Invalid student ID format: {student_id}"}

    if not session:
        return {"error": "Cassandra not connected"}

    student = None
    if "id" in filters:
        rows = session.execute("SELECT * FROM students WHERE id = %s", [filters["id"]])
        student = rows.one()
    elif "name" in filters:
        rows = session.execute("SELECT * FROM students WHERE name = %s ALLOW FILTERING", [filters["name"]])
        student = rows.one()

    if not student:
        return {"error": "Student not found"}

    row = dict(student._asdict())

    # Prepare features
    input_data = []
    for col in feature_names:
        val = row.get(col)
        if col in encoders:
            val = encoders[col].transform([val])[0] if val in encoders[col].classes_ else -1
        input_data.append(val)

    X = pd.DataFrame([input_data], columns=feature_names)
    prediction = model.predict(X)[0]
    probability = model.predict_proba(X)[0][1]

    # Explanation generation
    cgpa = row.get("overallcgpa")
    num_failed = row.get("num_failed", 0)
    fail_phrase = "have not failed any subjects" if num_failed == 0 else f"failed {num_failed} subjects"
    explanation = (
        f"{'Yes' if prediction else 'No'} — this student is "
        f"{'likely' if prediction else 'unlikely'} to graduate with honors "
        f"because their CGPA is {cgpa} and they {fail_phrase}."
    )

    return {
        "id": row["id"],
        "name": row["name"],
        "cgpa": cgpa,
        "honors": bool(prediction),
        "confidence": round(probability, 4),
        "explanation": explanation
    }
