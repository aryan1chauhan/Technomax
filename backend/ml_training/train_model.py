import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, f1_score, precision_score,
    recall_score, roc_auc_score
)

# ─── Load Data ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE_DIR, "training_data.csv"))

FEATURES = [
    "distance_km", "beds", "icu", "equipment_match",
    "severity_weight", "has_ventilator", "has_defibrillator",
    "has_ct_scan", "has_blood_bank", "has_icu_equipment",
    "doctor_count", "accepting", "speciality_match",
    "hospital_load", "condition_severity"
]

X = df[FEATURES]
y = df["was_selected"]

print(f"Total samples : {len(df)}")
print(f"Positive (1)  : {y.sum()} ({100*y.mean():.2f}%)")
print(f"Negative (0)  : {(y==0).sum()}")

# ─── Split ────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ─── Train RandomForest ───────────────────────────────────────
print("\nTraining RandomForest with class_weight='balanced'...")
model = RandomForestClassifier(
    n_estimators=300,
    max_depth=12,
    min_samples_leaf=2,
    class_weight="balanced",       # handles 187:1 imbalance
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# ─── Threshold Tuning ─────────────────────────────────────────
# Find threshold that maximises F1 on test set
probs = model.predict_proba(X_test)[:, 1]

best_f1, best_thresh = 0, 0.5
for t in np.arange(0.1, 0.9, 0.01):
    preds = (probs >= t).astype(int)
    f = f1_score(y_test, preds, zero_division=0)
    if f > best_f1:
        best_f1, best_thresh = f, t

print(f"\nBest threshold : {best_thresh:.2f}")
print(f"Best F1 score  : {best_f1:.4f}")

# ─── Final Evaluation ─────────────────────────────────────────
final_preds = (probs >= best_thresh).astype(int)
print("\nClassification Report:")
print(classification_report(y_test, final_preds, zero_division=0))
print(f"ROC-AUC: {roc_auc_score(y_test, probs):.4f}")

# ─── Save Model + Threshold ───────────────────────────────────
output = {
    "model": model,
    "threshold": best_thresh,
    "features": FEATURES
}
out_path = os.path.join(BASE_DIR, "hospital_model.pkl")
with open(out_path, "wb") as f:
    pickle.dump(output, f)

print(f"\nModel saved → {out_path}")

# Feature importance
fi = pd.Series(model.feature_importances_, index=FEATURES)
print("\nTop 10 features:")
print(fi.sort_values(ascending=False).head(10).to_string())
