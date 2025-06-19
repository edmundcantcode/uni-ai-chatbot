import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os

# Load data
df = pd.read_csv("data/merged_for_training.csv")
used_features = [
    "gender", "race", "country", "programme", "year",
    "num_subjects", "num_failed", "avg_grade_score", "fail_rate"
]
X = df[used_features]
y = df["honors"]

# Encode
encoders = {}
for col in X.select_dtypes(include="object").columns:
    le = LabelEncoder()
    X[col] = le.fit_transform(X[col].astype(str))
    encoders[col] = le

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
print("=== Classification Report ===")
print(classification_report(y_test, y_pred))

# Save
os.makedirs("models", exist_ok=True)
joblib.dump(model, "models/honors_model.pkl")
joblib.dump(encoders, "models/label_encoders.pkl")
joblib.dump(used_features, "models/feature_names.pkl")
print("✅ Honors model and encoders saved.")
