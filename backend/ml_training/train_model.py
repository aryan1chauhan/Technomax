import pandas as pd
import numpy as np
import pickle
import math
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, f1_score, roc_auc_score
)

# ─── Load Data ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE_DIR, "training_data.csv"))

# NOTE: Features are ALREADY normalized in generate_dataset.py
# using the same functions as ml_scorer.py. Do NOT re-normalize here.
# Verify the ranges look sane (all should be 0-1)
print("Feature ranges (should all be 0-1, already normalized by generate_dataset.py):")
for col in ['distance_km', 'beds', 'icu', 'doctor_count', 'hospital_load']:
    lo, hi = df[col].min(), df[col].max()
    ok = "OK" if hi <= 1.1 else "RAW - NEEDS FIX"
    print(f"  {col:20s} {lo:.3f} - {hi:.3f}  [{ok}]")

# ─── Features ─────────────────────────────────────────────────
FEATURES = [
    "distance_km", "beds", "icu", "equipment_match",
    "severity_weight", "has_ventilator", "has_defibrillator",
    "has_ct_scan", "has_blood_bank", "has_icu_equipment",
    "doctor_count", "accepting", "speciality_match",
    "hospital_load", "condition_severity"
]

X = df[FEATURES]
y = df["was_selected"]

print(f"\nTotal samples : {len(df)}")
print(f"Positive (1)  : {y.sum()} ({100*y.mean():.2f}%)")
print(f"Negative (0)  : {(y==0).sum()}")

# ─── Split ────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ─── Train ────────────────────────────────────────────────────
print("\nTraining RandomForest with class_weight='balanced'...")
model = RandomForestClassifier(
    n_estimators=300,
    max_depth=12,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# ─── Threshold Tuning ─────────────────────────────────────────
probs = model.predict_proba(X_test)[:, 1]
best_f1, best_thresh = 0, 0.5
for t in np.arange(0.1, 0.9, 0.01):
    preds = (probs >= t).astype(int)
    f = f1_score(y_test, preds, zero_division=0)
    if f > best_f1:
        best_f1, best_thresh = f, t

print(f"\nBest threshold : {best_thresh:.2f}")
print(f"Best F1 score  : {best_f1:.4f}")

# ─── Evaluation ───────────────────────────────────────────────
final_preds = (probs >= best_thresh).astype(int)
print("\nClassification Report:")
print(classification_report(y_test, final_preds, zero_division=0))
print(f"ROC-AUC: {roc_auc_score(y_test, probs):.4f}")

# ─── Feature importance check ─────────────────────────────────
fi = pd.Series(model.feature_importances_, index=FEATURES)
fi_sorted = fi.sort_values(ascending=False)
print("\nFeature Importances (distance_km should be top 3):")
for i, (feat, imp) in enumerate(fi_sorted.items(), 1):
    marker = " <--" if feat == "distance_km" else ""
    print(f"  {i:2d}. {feat:22s} {imp:.4f}{marker}")

# Warn if distance is still underweighted after fix
dist_rank = list(fi_sorted.index).index("distance_km") + 1
if dist_rank > 4:
    print(f"\n!! WARNING: distance_km ranked #{dist_rank} -- check generate_dataset.py normalization")
else:
    print(f"\n>> distance_km ranked #{dist_rank} -- normalization fix working correctly!")

# ─── Save ─────────────────────────────────────────────────────
output = {
    "model":     model,
    "threshold": best_thresh,
    "features":  FEATURES,
    "normalization": {
        "beds":         "log(1+x)/log(502)",
        "hospital_load":"log(1+x)/log(502)",
        "icu":          "min(x/50, 1.0)",
        "doctor_count": "min(x/20, 1.0)",
        "distance_km":  "1/(1+x*0.1)  [higher=closer]",
    }
}
out_path = os.path.join(BASE_DIR, "hospital_model.pkl")
with open(out_path, "wb") as f:
    pickle.dump(output, f)

print(f"\nModel saved: {out_path}")
