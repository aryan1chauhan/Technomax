import os
import joblib
import numpy as np
from app.engine.haversine import calculate_distance
from app.engine.scorer import find_best_hospital

MODEL_PATH = os.path.join(
    os.path.dirname(__file__), 
    '../../ml_training/hospital_model.pkl'
)

try:
    ml_model = joblib.load(MODEL_PATH)
    ML_AVAILABLE = True
    print("ML model loaded successfully")
except Exception:
    ml_model = None
    ML_AVAILABLE = False
    print("ML model not found — using rule-based scoring")

OPTIMAL_THRESHOLD = 0.9778

SEVERITY_MAP = {
    'cardiac arrest': 3,
    'stroke': 3,
    'trauma': 3,
    'severe trauma': 3,
    'respiratory failure': 3,
    'head injury': 3,
    'internal bleeding': 3,
    'spinal injury': 3,
    'chest injury': 3,
    'burns': 2,
    'anaphylaxis': 2,
    'kidney failure': 2,
    'pelvic injury': 2,
    'hypoglycemic crisis': 2,
    'severe bleeding': 3,
    'fractures': 1,
    'soft tissue injury': 1,
    'facial injury': 1,
    'psychological trauma': 1,
    'broken bone': 1,
    'mild allergic reaction': 1,
}

CONDITION_SPECIALITY_MAP = {
    'cardiac arrest':      ['defibrillator', 'ventilator', 'icu'],
    'stroke':              ['ct_scan', 'icu'],
    'trauma':              ['blood_bank', 'ventilator', 'icu'],
    'severe trauma':       ['blood_bank', 'ventilator', 'icu'],
    'respiratory failure': ['ventilator', 'icu'],
    'head injury':         ['ct_scan', 'icu'],
    'internal bleeding':   ['blood_bank', 'icu'],
    'spinal injury':       ['ct_scan', 'icu'],
    'chest injury':        ['ventilator', 'defibrillator'],
    'burns':               ['blood_bank'],
    'anaphylaxis':         ['ventilator'],
    'kidney failure':      ['icu'],
    'pelvic injury':       ['blood_bank', 'ct_scan'],
    'hypoglycemic crisis': ['icu'],
    'severe bleeding':     ['blood_bank'],
    'fractures':           [],
    'soft tissue injury':  [],
    'facial injury':       [],
    'psychological trauma':[],
    'broken bone':         [],
    'mild allergic reaction': [],
}

def predict_best_hospital(
    hospitals: list[dict],
    equipment_needed: list[str],
    ambulance_lat: float,
    ambulance_lng: float,
    condition: str = ''
) -> dict | None:

    if not ML_AVAILABLE:
        return find_best_hospital(
            hospitals, equipment_needed, 
            ambulance_lat, ambulance_lng
        )

    if not hospitals:
        return None

    scored = []
    needed = set(equipment_needed)
    condition_severity = SEVERITY_MAP.get(condition.lower(), 1)
    speciality_needed = CONDITION_SPECIALITY_MAP.get(condition.lower(), [])

    for hospital in hospitals:
        # Filter: skip if accepting=False or beds=0
        if not hospital.get('accepting', True) or hospital.get('beds', 0) == 0:
            continue
            
        distance_km = calculate_distance(
            ambulance_lat, ambulance_lng, 
            hospital['lat'], hospital['lng']
        )
        
        avail = set(hospital.get('equipment', []))
        
        equipment_match = len(needed & avail) / len(needed) if needed else 1.0

        # New feature: speciality_match
        if speciality_needed:
            spec_match_count = sum(1 for item in speciality_needed if item in avail)
            speciality_match = spec_match_count / len(speciality_needed)
        else:
            speciality_match = 1.0

        # New feature: hospital_load proxy
        beds_val = hospital.get('beds', 0) or 0
        hospital_load = min(beds_val / 30, 1.0)
            
        # Build feature vector (must match train order exactly — 15 features)
        features = [
            distance_km,
            beds_val,
            hospital.get('icu', 0),
            equipment_match,
            condition_severity,
            1 if 'ventilator' in avail else 0,
            1 if 'defibrillator' in avail else 0,
            1 if 'ct_scan' in avail else 0,
            1 if 'blood_bank' in avail else 0,
            1 if 'icu' in avail else 0,
            hospital.get('doctors', 0),
            1 if hospital.get('accepting', True) else 0,
            speciality_match,
            hospital_load,
            condition_severity,
        ]
        
        prob = float(ml_model.predict_proba([features])[0][1])
        # Use optimal threshold instead of default 0.5
        is_selected = prob >= OPTIMAL_THRESHOLD
        
        equipment_matched = list(needed & avail)
        equipment_missing = list(needed - avail)
        eta_minutes = round((distance_km / 40) * 60)
        
        scored.append({
            **hospital,
            'ml_score': float(round(prob, 4)),
            'final_score': float(round(prob, 4)),
            'is_selected': is_selected,
            'distance_km': float(round(distance_km, 2)),
            'eta_minutes': eta_minutes,
            'equipment_matched': equipment_matched,
            'equipment_missing': equipment_missing
        })

    if not scored:
        return None

    # First try hospitals above threshold
    selected = [h for h in scored if h.get('is_selected')]

    if selected:
        selected.sort(key=lambda x: x['ml_score'], reverse=True)
        return selected[0]
    else:
        # Fallback: return highest scoring hospital regardless
        scored.sort(key=lambda x: x['ml_score'], reverse=True)
        return scored[0] if scored else None
