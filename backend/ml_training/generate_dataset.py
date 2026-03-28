import os
import random
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import math

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
DATABASE_URL = os.getenv('DATABASE_URL')

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ─── Normalization functions ──────────────────────────────────
# CRITICAL: These MUST be identical to ml_scorer.py so the model
# trains on the exact same feature scale it sees at inference.

def log_normalize_beds(beds):
    """Matches ml_scorer._log_normalize_beds exactly."""
    return min(math.log(1 + max(float(beds), 0)) / math.log(502), 1.0)

def normalize_distance(km):
    """1/(1 + km*0.1) — closer = higher value."""
    return 1 / (1 + float(km) * 0.1)

def normalize_icu(icu):
    return min(float(icu) / 50, 1.0)

def normalize_doctors(doctors):
    return min(float(doctors) / 20, 1.0)

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

CONDITION_SEVERITY_MAP = {
    'cardiac arrest': 3, 'stroke': 3, 'trauma': 3, 'severe trauma': 3,
    'respiratory failure': 3, 'head injury': 3, 'internal bleeding': 3,
    'spinal injury': 3, 'chest injury': 3, 'severe bleeding': 3,
    'burns': 2, 'anaphylaxis': 2, 'kidney failure': 2,
    'pelvic injury': 2, 'hypoglycemic crisis': 2,
    'fractures': 1, 'soft tissue injury': 1, 'facial injury': 1,
    'psychological trauma': 1, 'broken bone': 1, 'mild allergic reaction': 1,
    'other': 1,
}

# KEY FIX: how many negative hospitals to sample per case
NEGATIVES_PER_CASE = 7

def extract_equipment(raw):
    if isinstance(raw, list):
        return [e.lower() for e in raw if e]
    elif isinstance(raw, str):
        return [e.strip().lower() for e in raw.strip('{}').split(',') if e.strip()]
    return []

def build_features(hospital, needed_items, speciality_needed, case_lat, case_lng, condition_severity, condition_clean):
    avail_items = extract_equipment(hospital.get('equipment', []))
    beds_val = int(hospital.get('beds', 0) or 0)
    icu_val = int(hospital.get('icu', 0) or 0)
    raw_distance_km = haversine_distance(
        case_lat, case_lng,
        float(hospital.get('lat', 0) or 0),
        float(hospital.get('lng', 0) or 0)
    )
    equipment_match = (
        sum(1 for item in needed_items if item in avail_items) / len(needed_items)
        if needed_items else 1.0
    )

    specialists = hospital.get('specialists', {})
    if isinstance(specialists, str):
        try:
            specialists = json.loads(specialists)
        except:
            specialists = {}
    needed_specialist = CONDITION_SPECIALIST_MAP.get(condition_clean, '')
    specialist_present = int(specialists.get(needed_specialist, 0) > 0)

    # FIX: Normalize ALL continuous features to match ml_scorer.py inference
    # Previously these were raw values (beds=300, distance_km=45.2, doctors=18)
    # but ml_scorer.py sends normalized 0-1 values — mismatch killed the model
    return {
        'distance_km':       normalize_distance(raw_distance_km),  # 0-1, higher=closer
        'beds':              log_normalize_beds(beds_val),          # 0-1, log-scaled
        'icu':               normalize_icu(icu_val),                # 0-1, capped at 50
        'equipment_match':   equipment_match,
        'severity_weight':   condition_severity / 3.0,
        'has_ventilator':    1 if 'ventilator'    in avail_items else 0,
        'has_defibrillator': 1 if 'defibrillator' in avail_items else 0,
        'has_ct_scan':       1 if 'ct_scan'       in avail_items else 0,
        'has_blood_bank':    1 if 'blood_bank'    in avail_items else 0,
        'has_icu_equipment': 1 if 'icu'           in avail_items else 0,
        'accepting':         1 if hospital.get('accepting', True) else 0,
        'specialist_present': specialist_present,
        'hospital_load':     min(hospital.get('active_cases', 0) / 20.0, 1.0),
        'condition_severity': condition_severity,
        'ot_available':      min(hospital.get('ot_available', 0) / 6.0, 1.0),
    }

def generate_dataset():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in .env")
        return

    engine = create_engine(DATABASE_URL)

    try:
        cases_df = pd.read_sql("SELECT * FROM cases", engine)
        hospitals_df = pd.read_sql("""
            SELECT h.id, h.name, h.lat, h.lng,
                   a.beds, a.icu, a.doctors,
                   a.equipment, a.accepting, a.ot_available, a.specialists, a.active_cases
            FROM hospitals h
            JOIN availabilities a ON a.hospital_id = h.id
        """, engine)
    except Exception as e:
        print(f"Error reading from database: {e}")
        return

    hospitals_list = hospitals_df.to_dict('records')
    hospitals_by_id = {h['id']: h for h in hospitals_list}

    training_data = []
    skipped = 0

    for _, case in cases_df.iterrows():
        assigned_hosp_id = case.get('assigned_hospital_id')
        if not assigned_hosp_id or assigned_hosp_id not in hospitals_by_id:
            skipped += 1
            continue

        needed_items = extract_equipment(case.get('equipment_needed', []))
        case_lat = float(case.get('ambulance_lat', 0.0) or 0.0)
        case_lng = float(case.get('ambulance_lng', 0.0) or 0.0)
        condition_str = str(case.get('condition', '')).lower()
        condition_severity = CONDITION_SEVERITY_MAP.get(condition_str, 1)
        speciality_needed = CONDITION_SPECIALITY_MAP.get(condition_str, [])

        # --- POSITIVE: the hospital that was actually selected ---
        selected_hospital = hospitals_by_id[assigned_hosp_id]
        pos_features = build_features(
            selected_hospital, needed_items, speciality_needed,
            case_lat, case_lng, condition_severity, condition_str
        )
        pos_features['was_selected'] = 1
        training_data.append(pos_features)

        # --- NEGATIVES: sample NEGATIVES_PER_CASE other hospitals ---
        other_hospitals = [
            h for h in hospitals_list
            if h['id'] != assigned_hosp_id
        ]
        # Bias negatives toward geographically close hospitals --
        # these are the hard negatives the model needs to learn to reject
        other_hospitals.sort(
            key=lambda h: haversine_distance(
                case_lat, case_lng,
                float(h.get('lat', 0) or 0),
                float(h.get('lng', 0) or 0)
            )
        )
        # Take 2 nearest + 5 random from the rest for variety
        # This teaches the model that distance is a dominant rejection criteria
        near_negatives = other_hospitals[:min(2, len(other_hospitals))]
        far_pool = other_hospitals[min(2, len(other_hospitals)):]
        rand_negatives = random.sample(far_pool, min(5, len(far_pool)))
        selected_negatives = near_negatives + rand_negatives

        for neg_hospital in selected_negatives:
            neg_features = build_features(
                neg_hospital, needed_items, speciality_needed,
                case_lat, case_lng, condition_severity, condition_str
            )
            neg_features['was_selected'] = 0
            training_data.append(neg_features)

    # SYNTHETIC BOOST: inject specialist-critical cases
    # so the model learns specialist_present matters for severity=3 conditions
    SPECIALIST_CONDITIONS = [
        ("cardiac arrest", 3, ["defibrillator", "ventilator", "icu_equipment"]),
        ("stroke", 3, ["ct_scan", "icu_equipment"]),
        ("spinal injury", 3, ["ct_scan", "ventilator", "icu_equipment"]),
        ("kidney failure", 2, ["icu_equipment", "blood_bank"]),
        ("burns", 2, ["blood_bank", "ventilator"]),
    ]

    for condition_str, sev, needed_equip in SPECIALIST_CONDITIONS:
        for _ in range(10):  # 10 synthetic cases per condition to prevent dataset wash-out
            case_lat = random.uniform(29.5, 31.0)
            case_lng = random.uniform(77.5, 80.0)
            
            # Positive: hospital WITH specialist, moderate distance
            specialist_hospitals = [
                h for h in hospitals_list
                if CONDITION_SPECIALIST_MAP.get(condition_str, '') in 
                (h.get('specialists') or {})
            ]
            if not specialist_hospitals:
                continue
            specialist_hospitals.sort(
                key=lambda h: haversine_distance(
                    case_lat, case_lng,
                    float(h.get('lat', 0) or 0),
                    float(h.get('lng', 0) or 0)
                )
            )
            pos_h = random.choice(specialist_hospitals[:2])
            pos_feat = build_features(pos_h, needed_equip, [], case_lat, case_lng, sev, condition_str)
            pos_feat['was_selected'] = 1
            training_data.append(pos_feat)
            
            # Negative: nearby hospital WITHOUT specialist
            no_specialist = [
                h for h in hospitals_list
                if CONDITION_SPECIALIST_MAP.get(condition_str, '') not in
                (h.get('specialists') or {})
            ]
            for neg_h in random.sample(no_specialist, min(4, len(no_specialist))):
                neg_feat = build_features(neg_h, needed_equip, [], case_lat, case_lng, sev, condition_str)
                neg_feat['was_selected'] = 0
                training_data.append(neg_feat)

    df = pd.DataFrame(training_data)

    pos = (df['was_selected'] == 1).sum()
    neg = (df['was_selected'] == 0).sum()
    print(f"Generated {len(df)} training samples")
    print(f"Positives: {pos} | Negatives: {neg} | Ratio: 1:{round(neg/pos, 1)}")
    print(f"Skipped cases (no matching hospital): {skipped}")

    # Sanity-check normalized ranges
    for col in ['distance_km', 'beds', 'icu', 'ot_available']:
        lo, hi = df[col].min(), df[col].max()
        print(f"  {col:20s} range: {lo:.3f} - {hi:.3f}")

    output_path = os.path.join(os.path.dirname(__file__), 'training_data.csv')
    df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")

if __name__ == '__main__':
    generate_dataset()
