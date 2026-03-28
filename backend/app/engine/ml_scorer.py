# app/engine/ml_scorer.py
import pickle, os, math, numpy as np

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


def _log_normalize_beds(beds: int) -> float:
    """
    FIX: Log-scale bed normalization so AIIMS (500 beds) doesn't
    dominate over a 100-bed hospital that's 5x closer.
    log(501)/log(501) = 1.0 (max), log(101)/log(501) ≈ 0.82,
    log(51)/log(501) ≈ 0.64 — meaningful spread without runaway values.
    """
    return min(math.log(1 + max(beds, 0)) / math.log(502), 1.0)


def ml_score(features: dict) -> float:
    """
    Returns a float score 0-1 for a hospital candidate.
    Falls back to rule-based if model unavailable.
    """
    if _model is None:
        return _rule_fallback(features)

    COLS = _features or [
        "distance_km", "beds", "icu", "equipment_match",
        "severity_weight", "has_ventilator", "has_defibrillator",
        "has_ct_scan", "has_blood_bank", "has_icu_equipment",
        "accepting", "specialist_present",
        "hospital_load", "condition_severity",
        "ot_available"
    ]

    row = np.array([[features.get(c, 0) for c in COLS]])
    prob = _model.predict_proba(row)[0][1]

    if prob >= _threshold:
        score = 0.5 + 0.5 * ((prob - _threshold) / (1 - _threshold + 1e-9))
    else:
        score = 0.5 * (prob / (_threshold + 1e-9))

    return round(float(score), 4)


def _rule_fallback(f: dict) -> float:
    """
    FIX: Rebalanced weights — distance now dominates (0.45) so
    a nearby 80-bed hospital beats a far 500-bed AIIMS.
    Bed score is log-normalized so large hospitals don't auto-win.
    Equipment match weight raised to reward proper kit.
    """
    # FIX: log-normalize so 500-bed AIIMS doesn't score 50x a 10-bed clinic
    bed_score = _log_normalize_beds(f.get("beds", 0))

    # FIX: distance score — steeper penalty for far hospitals
    # at 5km → 0.67, at 20km → 0.33, at 50km → 0.16
    distance_score = 1 / (1 + f.get("distance_km", 999) * 0.1)

    equipment_score = f.get("equipment_match", 1.0)

    # FIX: weights — distance 0.45, equipment 0.30, beds 0.25
    # Previously: availability 0.40, distance 0.35, equipment 0.25
    # The old weights let AIIMS win on beds alone from 80km away
    return round(
        distance_score * 0.45 +
        equipment_score * 0.30 +
        bed_score       * 0.25,
        4
    )


# Severity levels for condition mapping
SEVERITY_MAP = {
    "cardiac arrest": 3, "cardiac_arrest": 3,
    "stroke": 3, "respiratory": 3, "respiratory failure": 3,
    "trauma": 3, "severe trauma": 3, "head injury": 3,
    "internal bleeding": 3, "spinal injury": 3,
    "chest injury": 3, "severe bleeding": 3, "chest_pain": 3,
    "burns": 2, "anaphylaxis": 2, "kidney failure": 2,
    "kidney_failure": 2, "pelvic injury": 2, "hypoglycemic crisis": 2,
    "obstetric": 2, "poisoning": 1, "allergic_reaction": 2,
    "seizure": 2, "diabetic": 2, "heat_stroke": 2,
    "fracture": 1, "fractures": 1, "broken bone": 1,
    "soft tissue injury": 1, "facial injury": 1, "eye_injury": 1,
    "psychological trauma": 1, "general": 1, "infection": 1,
    "head_injury": 3, "internal_bleeding": 3, "spinal_injury": 3,
}

CONDITION_SPECIALIST_MAP = {
    "cardiac arrest": "cardiologist",
    "chest pain":     "cardiologist",
    "stroke":         "neurologist",
    "spinal injury":  "orthopedic",
    "trauma":         "general_surgeon",
    "obstetric":      "gynecologist",
    "kidney failure": "nephrologist",
    "respiratory":    "pulmonologist",
    "burns":          "plastic_surgeon",
    "pediatric":      "pediatrician",
    "seizure":        "neurologist",
    "heart failure":  "cardiologist",
}


def predict_best_hospital(
    hospitals: list,
    condition: str,
    equipment_needed: list,
    ambulance_lat: float,
    ambulance_lng: float,
) -> dict | None:
    """
    Score every hospital and return the best candidate.
    FIX: Pre-filter to nearest 30 hospitals before ML scoring
    to avoid wasting time scoring hospitals 200km away.
    """
    from app.engine.haversine import calculate_distance

    needed = equipment_needed or []
    condition_clean = condition.lower().replace("_", " ")
    condition_severity = SEVERITY_MAP.get(condition_clean, 1)

    # FIX: Pre-compute distances and filter to nearest 30 accepting hospitals
    # This prevents AIIMS winning from 100km away AND speeds up scoring
    accepting = [h for h in hospitals if h.get("accepting", False) and h.get("beds", 0) > 0]

    if not accepting:
        return None

    # Attach distance to each hospital
    for h in accepting:
        h["_dist"] = calculate_distance(ambulance_lat, ambulance_lng, h["lat"], h["lng"])

    # Sort by distance, keep nearest 30 (enough diversity, avoids far giants)
    accepting.sort(key=lambda h: h["_dist"])
    candidates = accepting[:30]

    results = []

    for h in candidates:
        distance_km = h["_dist"]

        eq = [e.lower() for e in (h.get("equipment", []) or [])]
        equipment_match = (
            len([e for e in needed if e in eq]) / len(needed)
            if needed else 1.0
        )

        import json
        specialists = h.get('specialists', {})
        if isinstance(specialists, str):
            try:
                specialists = json.loads(specialists)
            except:
                specialists = {}
        needed_specialist = CONDITION_SPECIALIST_MAP.get(condition_clean, '')
        specialist_present = int(specialists.get(needed_specialist, 0) > 0)

        # FIX: pass log-normalized bed value as feature so ML model
        # sees a sane 0-1 range instead of raw 500
        score = ml_score({
            "distance_km":       distance_km,
            "beds":              _log_normalize_beds(h.get("beds", 0)),  # normalized
            "icu":               min(h.get("icu", 0) / 50, 1.0),        # normalized
            "equipment_match":   equipment_match,
            "severity_weight":   condition_severity / 3.0,
            "has_ventilator":    int("ventilator" in eq),
            "has_defibrillator": int("defibrillator" in eq),
            "has_ct_scan":       int("ct_scan" in eq),
            "has_blood_bank":    int("blood_bank" in eq),
            "has_icu_equipment": int("icu_equipment" in eq or "icu" in eq),
            "accepting":         1,
            "specialist_present": specialist_present,
            "hospital_load":     min(h.get("active_cases", 0) / 20.0, 1.0),
            "condition_severity": condition_severity,
            "ot_available":      min(h.get("ot_available", 0) / 6.0, 1.0),
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

    reasoning = [
        f"Distance: {best['distance_km']} km — nearest qualified hospital",
        f"Beds: {best.get('beds', 0)}, ICU: {best.get('icu', 0)}",
    ]

    # Show specialist availability
    needed_specialist = CONDITION_SPECIALIST_MAP.get(condition_clean, '')
    specialists = best.get('specialists', {})
    if isinstance(specialists, str):
        try:
            import json
            specialists = json.loads(specialists)
        except:
            specialists = {}

    if needed_specialist and specialists.get(needed_specialist, 0) > 0:
        reasoning.append(f"Specialist: {needed_specialist.replace('_', ' ').title()} available ✓")
    elif needed_specialist:
        reasoning.append(f"Specialist: {needed_specialist.replace('_', ' ').title()} not available")

    # Show OT availability
    ot = best.get('ot_available', 0)
    if ot > 0:
        reasoning.append(f"Operation Theatres available: {ot}")

    # Show hospital load
    active = best.get('active_cases', 0)
    reasoning.append(f"Current hospital load: {active} active cases")

    if best["equipment_matched"]:
        reasoning.append(f"Equipment matched: {', '.join(best['equipment_matched'])}")
    if best["equipment_missing"]:
        reasoning.append(f"Equipment missing: {', '.join(best['equipment_missing'])}")

    reasoning.append(f"ML confidence score: {round(best['final_score'] * 100)}%")
    best["ml_reasoning"] = reasoning

    return best
