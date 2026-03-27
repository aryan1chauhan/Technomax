import os
import random
import math
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
DATABASE_URL = os.getenv('DATABASE_URL')

CONDITIONS = {
    'cardiac arrest':       {'severity': 3, 'equipment': ['defibrillator', 'ventilator']},
    'stroke':               {'severity': 3, 'equipment': ['ct_scan']},
    'trauma':               {'severity': 3, 'equipment': ['blood_bank', 'ventilator']},
    'severe trauma':        {'severity': 3, 'equipment': ['blood_bank', 'ventilator']},
    'respiratory failure':  {'severity': 3, 'equipment': ['ventilator']},
    'head injury':          {'severity': 3, 'equipment': ['ct_scan']},
    'internal bleeding':    {'severity': 3, 'equipment': ['blood_bank']},
    'spinal injury':        {'severity': 3, 'equipment': ['ct_scan']},
    'chest injury':         {'severity': 3, 'equipment': ['ventilator', 'defibrillator']},
    'severe bleeding':      {'severity': 3, 'equipment': ['blood_bank']},
    'burns':                {'severity': 2, 'equipment': ['blood_bank']},
    'anaphylaxis':          {'severity': 2, 'equipment': ['ventilator']},
    'kidney failure':       {'severity': 2, 'equipment': []},
    'pelvic injury':        {'severity': 2, 'equipment': ['blood_bank', 'ct_scan']},
    'hypoglycemic crisis':  {'severity': 2, 'equipment': []},
    'fractures':            {'severity': 1, 'equipment': []},
    'soft tissue injury':   {'severity': 1, 'equipment': []},
    'facial injury':        {'severity': 1, 'equipment': []},
    'psychological trauma': {'severity': 1, 'equipment': []},
    'broken bone':          {'severity': 1, 'equipment': []},
}

DISTRICTS = [
    {'name': 'Roorkee',  'lat_min': 29.82, 'lat_max': 29.90, 'lng_min': 77.85, 'lng_max': 77.95},
    {'name': 'Haridwar', 'lat_min': 29.88, 'lat_max': 29.98, 'lng_min': 78.10, 'lng_max': 78.20},
    {'name': 'Dehradun', 'lat_min': 30.28, 'lat_max': 30.38, 'lng_min': 78.00, 'lng_max': 78.10},
    {'name': 'Haldwani', 'lat_min': 29.18, 'lat_max': 29.25, 'lng_min': 79.48, 'lng_max': 79.55},
    {'name': 'Nainital', 'lat_min': 29.36, 'lat_max': 29.42, 'lng_min': 79.43, 'lng_max': 79.48},
]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def log_normalize_beds(beds):
    """FIX: Must match ml_scorer.py exactly so training data = inference."""
    return math.log(1 + max(beds, 0)) / math.log(502)

def generate():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in .env")
        return

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT h.id, h.name, h.lat, h.lng, a.beds, a.icu, a.equipment, a.accepting "
            "FROM hospitals h JOIN availabilities a ON a.hospital_id = h.id"
        )).fetchall()

    hospitals = []
    for r in rows:
        eq_raw = r[6]
        if isinstance(eq_raw, list):
            eq = [e.lower() for e in eq_raw if e]
        elif isinstance(eq_raw, str):
            eq = [e.strip().lower() for e in eq_raw.strip('{}').split(',') if e.strip()]
        else:
            eq = []
        hospitals.append({
            'id': r[0], 'name': r[1], 'lat': float(r[2]), 'lng': float(r[3]),
            'beds': r[4], 'icu': r[5], 'equipment': eq,
            'accepting': r[7] if r[7] is not None else True
        })

    if not hospitals:
        print("No hospitals found in database!")
        return

    print(f"Found {len(hospitals)} hospitals")

    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM cases WHERE user_id = 4"))
        conn.commit()
        print(f"Deleted {result.rowcount} old synthetic cases")

    cases_to_insert = []
    cases_per_condition = 30

    for condition, info in CONDITIONS.items():
        needed_eq = info['equipment']
        count = 0

        for _ in range(cases_per_condition):
            district = random.choice(DISTRICTS)
            amb_lat = random.uniform(district['lat_min'], district['lat_max'])
            amb_lng = random.uniform(district['lng_min'], district['lng_max'])

            accepting = [h for h in hospitals if h['beds'] > 0 and h['accepting']]
            if not accepting:
                accepting = hospitals

            # FIX: Pre-filter nearest 30 — matches inference behaviour in ml_scorer.py
            for h in accepting:
                h['_dist'] = haversine(amb_lat, amb_lng, h['lat'], h['lng'])
            accepting.sort(key=lambda h: h['_dist'])
            candidates = accepting[:30]

            best_hospital = None
            best_score = -1

            for h in candidates:
                dist = h['_dist']

                if needed_eq:
                    eq_match = sum(1 for e in needed_eq if e in h['equipment']) / len(needed_eq)
                else:
                    eq_match = 1.0

                # FIX: Use IDENTICAL formula to ml_scorer._rule_fallback
                # distance 0.45, equipment 0.30, beds (log-normalized) 0.25
                bed_score = log_normalize_beds(h['beds'])
                distance_score = 1 / (1 + dist * 0.1)
                noise = random.uniform(-0.03, 0.03)
                score = (distance_score * 0.45) + (eq_match * 0.30) + (bed_score * 0.25) + noise

                # Equipment bonuses (kept, but smaller to not override distance)
                if 'defibrillator' in needed_eq and 'defibrillator' in h['equipment']:
                    score += 0.15
                if 'ct_scan' in needed_eq and 'ct_scan' in h['equipment']:
                    score += 0.10
                if 'blood_bank' in needed_eq and 'blood_bank' in h['equipment']:
                    score += 0.10

                if score > best_score:
                    best_score = score
                    best_hospital = h

            if not best_hospital:
                best_hospital = min(hospitals, key=lambda h: haversine(amb_lat, amb_lng, h['lat'], h['lng']))

            dist_km = haversine(amb_lat, amb_lng, best_hospital['lat'], best_hospital['lng'])
            eta_min = round((dist_km / 40) * 60)
            final_score = round(best_score, 4) if best_score > 0 else 0.5

            cases_to_insert.append({
                'user_id': 4,
                'condition': condition,
                'equipment_needed': needed_eq,
                'ambulance_lat': round(amb_lat, 6),
                'ambulance_lng': round(amb_lng, 6),
                'assigned_hospital_id': best_hospital['id'],
                'final_score': final_score,
                'distance_km': round(dist_km, 2),
                'eta_minutes': max(eta_min, 1),
            })
            count += 1

        print(f"  {condition}: {count} cases → district spread ensures variety")

    with engine.connect() as conn:
        for c in cases_to_insert:
            conn.execute(text(
                "INSERT INTO cases (user_id, condition, equipment_needed, ambulance_lat, ambulance_lng, "
                "assigned_hospital_id, final_score, distance_km, eta_minutes) "
                "VALUES (:user_id, :condition, :equipment_needed, :ambulance_lat, :ambulance_lng, "
                ":assigned_hospital_id, :final_score, :distance_km, :eta_minutes)"
            ), c)
        conn.commit()

    print(f"\nTotal inserted: {len(cases_to_insert)} synthetic cases")
    print(f"({cases_per_condition} per condition × {len(CONDITIONS)} conditions)")

    # Show top-5 most-selected hospitals to verify AIIMS no longer dominates
    from collections import Counter
    hospital_counts = Counter(c['assigned_hospital_id'] for c in cases_to_insert)
    top5 = hospital_counts.most_common(5)
    hosp_names = {h['id']: h['name'] for h in hospitals}
    print("\nTop 5 most-selected hospitals (should be spread across districts):")
    for hid, cnt in top5:
        pct = cnt / len(cases_to_insert) * 100
        print(f"  {hosp_names.get(hid, hid)}: {cnt} cases ({pct:.1f}%)")

if __name__ == '__main__':
    generate()
