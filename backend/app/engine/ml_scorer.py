# app/engine/ml_scorer.py
import pickle, os, numpy as np

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_MODEL_PATH = os.path.join(_BASE, "ml_training", "hospital_model.pkl")

_model = None
_threshold = 0.5
_features = None

def _load():
    global _model, _threshold, _features
    if os.path.exists(_MODEL_PATH):
        with open(_MODEL_PATH, "rb") as f:
            data = pickle.load(f)
        # Support both old (bare model) and new (dict) format
        if isinstance(data, dict):
            _model = data["model"]
            _threshold = data.get("threshold", 0.5)
            _features = data.get("features")
        else:
            _model = data
            _threshold = 0.5
        print(f"[ML] Model loaded. Threshold={_threshold:.2f}")
    else:
        print("[ML] No model file found — using rule-based fallback")

_load()

def ml_score(features: dict) -> float:
    """
    Returns a float score 0-1 for a hospital candidate.
    Falls back to rule-based if model unavailable.
    """
    if _model is None:
        return _rule_fallback(features)

    COLS = _features or [
        "distance_km","beds","icu","equipment_match",
        "severity_weight","has_ventilator","has_defibrillator",
        "has_ct_scan","has_blood_bank","has_icu_equipment",
        "doctor_count","accepting","speciality_match",
        "hospital_load","condition_severity"
    ]

    row = np.array([[features.get(c, 0) for c in COLS]])
    prob = _model.predict_proba(row)[0][1]

    # Scale: prob above threshold maps to 0.5-1.0,
    # below threshold maps to 0.0-0.5
    # This keeps score meaningful for ranking
    if prob >= _threshold:
        score = 0.5 + 0.5 * ((prob - _threshold) / (1 - _threshold + 1e-9))
    else:
        score = 0.5 * (prob / (_threshold + 1e-9))

    return round(float(score), 4)


def _rule_fallback(f: dict) -> float:
    availability = min(f.get("beds", 0) / 10, 1.0)
    distance_score = 1 / (1 + f.get("distance_km", 999))
    equipment_score = f.get("equipment_match", 1.0)
    return round(
        availability * 0.40 +
        distance_score * 0.35 +
        equipment_score * 0.25, 4
    )


def predict_best_hospital(
    hospitals: list,
    condition: str,
    equipment_needed: list,
    ambulance_lat: float,
    ambulance_lng: float,
) -> dict | None:
    """
    Score every hospital using the ML model (or rule-based fallback)
    and return the single best candidate as a dict, or None.
    """
    from app.engine.haversine import calculate_distance

    SEVERITY_MAP = {
        "cardiac_arrest": 3, "cardiac arrest": 3,
        "stroke": 3, "respiratory": 3, "respiratory failure": 3,
        "trauma": 3, "severe trauma": 3, "head injury": 3,
        "internal bleeding": 3, "spinal injury": 3,
        "chest injury": 3, "severe bleeding": 3,
        "burns": 2, "anaphylaxis": 2, "kidney failure": 2,
        "pelvic injury": 2, "hypoglycemic crisis": 2,
        "obstetric": 2, "poisoning": 1,
        "fracture": 1, "fractures": 1, "broken bone": 1,
        "soft tissue injury": 1, "facial injury": 1,
        "psychological trauma": 1, "general": 1,
    }

    needed = equipment_needed or []
    condition_severity = SEVERITY_MAP.get(condition.lower().replace("_", " "), 1)
    results = []
    reasoning_parts = []

    for h in hospitals:
        if not h.get("accepting", False):
            continue

        distance_km = calculate_distance(
            ambulance_lat, ambulance_lng, h["lat"], h["lng"]
        )

        eq = [e.lower() for e in (h.get("equipment", []) or [])]
        equipment_match = (
            len([e for e in needed if e in eq]) / len(needed)
            if needed else 1.0
        )

        score = ml_score({
            "distance_km":       distance_km,
            "beds":              h.get("beds", 0),
            "icu":               h.get("icu", 0),
            "equipment_match":   equipment_match,
            "severity_weight":   condition_severity / 3.0,
            "has_ventilator":    int("ventilator" in eq),
            "has_defibrillator": int("defibrillator" in eq),
            "has_ct_scan":       int("ct_scan" in eq),
            "has_blood_bank":    int("blood_bank" in eq),
            "has_icu_equipment": int("icu_equipment" in eq or "icu" in eq),
            "doctor_count":      h.get("doctors", 0),
            "accepting":         int(h.get("accepting", False)),
            "speciality_match":  int(condition.lower().replace("_", " ") in (h.get("speciality", "") or "").lower()),
            "hospital_load":     min(h.get("beds", 0) / 30, 1.0),
            "condition_severity": condition_severity,
        })

        matched = [e for e in needed if e in eq]
        missing = [e for e in needed if e not in eq]

        results.append({
            **h,
            "final_score":       round(score, 4),
            "confidence":        round(score, 4),
            "distance_km":       round(distance_km, 2),
            "eta_minutes":       max(round((distance_km / 40) * 60), 1),
            "equipment_matched": matched,
            "equipment_missing": missing,
        })

    if not results:
        return None

    results.sort(key=lambda x: x["final_score"], reverse=True)
    best = results[0]

    # Build explainable reasoning
    reasoning = []
    reasoning.append(f"Distance: {best['distance_km']} km")
    reasoning.append(f"Beds: {best.get('beds', 0)}, ICU: {best.get('icu', 0)}")
    if best["equipment_matched"]:
        reasoning.append(f"Equipment matched: {', '.join(best['equipment_matched'])}")
    if best["equipment_missing"]:
        reasoning.append(f"Equipment missing: {', '.join(best['equipment_missing'])}")
    reasoning.append(f"ML score: {best['final_score']}")
    best["ml_reasoning"] = reasoning

    return best
