import pandas as pd
import random
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score

df = pd.read_csv("backend/clinic_slot_ml_dataset_20000_rows.csv")

print("Columns:", df.columns)

le_disease = LabelEncoder()
le_severity = LabelEncoder()
le_visit = LabelEncoder()

df['Disease_Type'] = le_disease.fit_transform(df['Disease_Type'])
df['Severity'] = le_severity.fit_transform(df['Severity'])
df['New_or_Followup'] = le_visit.fit_transform(df['New_or_Followup'])

X = df.drop('Consultation_Time', axis=1)
y = df['Consultation_Time']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestRegressor(
    n_estimators=120,
    max_depth=8,
    min_samples_split=5,
    random_state=42
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

print("\nModel Performance:")
print("MAE:", round(mean_absolute_error(y_test, y_pred), 3))
print("R2 Score:", round(r2_score(y_test, y_pred), 3))


joblib.dump(model, "consultation_model.pkl")
joblib.dump(le_disease, "le_disease.pkl")
joblib.dump(le_severity, "le_severity.pkl")
joblib.dump(le_visit, "le_visit.pkl")

print("\nModel and encoders saved successfully!")

def safe_transform(le, value):
    if value in le.classes_:
        return le.transform([value])[0]
    else:
        return -1  


sample = pd.DataFrame([{
    "Age": 25,
    "Disease_Type": safe_transform(le_disease, "Fever"),
    "Severity": safe_transform(le_severity, "Medium"),
    "New_or_Followup": safe_transform(le_visit, "New"),
    "Symptoms_Count": 4
}])

predicted_time = model.predict(sample)[0]


final_time = round(predicted_time + random.uniform(-2, 2), 1)

print("\nPredicted Consultation Time:", final_time, "minutes")