import os
import random
import math
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
DATABASE_URL = os.getenv('DATABASE_URL')

# All 20 conditions — EQUAL distribution across all of them
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

# 5 districts for ambulance location diversity
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

def generate():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in .env")
        return

    engine = create_engine(DATABASE_URL)

    # Load ALL hospitals with their equipment
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

    # DELETE all existing synthetic cases first
    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM cases WHERE user_id = 4"))
        conn.commit()
        print(f"Deleted {result.rowcount} old synthetic cases")

    cases_to_insert = []
    cases_per_condition = 30  # 30 × 20 conditions = 600 total

    for condition, info in CONDITIONS.items():
        needed_eq = info['equipment']
        count = 0

        for _ in range(cases_per_condition):
            # Pick random district
            district = random.choice(DISTRICTS)
            amb_lat = random.uniform(district['lat_min'], district['lat_max'])
            amb_lng = random.uniform(district['lng_min'], district['lng_max'])

            # Score each hospital using scorer.py formula
            best_hospital = None
            best_score = -1

            for h in hospitals:
                # Filter: beds > 0 AND accepting = True
                if h['beds'] <= 0:
                    continue
                if not h['accepting']:
                    continue

                # Equipment match (fraction of needed equipment the hospital has)
                if needed_eq:
                    eq_match = sum(1 for e in needed_eq if e in h['equipment']) / len(needed_eq)
                else:
                    eq_match = 1.0

                # Distance
                dist = haversine(amb_lat, amb_lng, h['lat'], h['lng'])
                distance_score = 1 / (1 + dist)

                # Base score — scorer.py formula
                score = (h['beds'] / 50 * 0.3) + (eq_match * 0.4) + (distance_score * 0.3)

                # Equipment-specific bonuses
                if 'defibrillator' in needed_eq and 'defibrillator' in h['equipment']:
                    score += 0.3
                if 'ct_scan' in needed_eq and 'ct_scan' in h['equipment']:
                    score += 0.2
                if 'blood_bank' in needed_eq and 'blood_bank' in h['equipment']:
                    score += 0.2

                if score > best_score:
                    best_score = score
                    best_hospital = h

            if not best_hospital:
                # Fallback: pick nearest
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

        print(f"  {condition}: {count} cases")

    # Batch insert
    with engine.connect() as conn:
        for c in cases_to_insert:
            conn.execute(text(
                "INSERT INTO cases (user_id, condition, equipment_needed, ambulance_lat, ambulance_lng, "
                "assigned_hospital_id, final_score, distance_km, eta_minutes) "
                "VALUES (:user_id, :condition, :equipment_needed, :ambulance_lat, :ambulance_lng, "
                ":assigned_hospital_id, :final_score, :distance_km, :eta_minutes)"
            ), {
                'user_id': c['user_id'],
                'condition': c['condition'],
                'equipment_needed': c['equipment_needed'],
                'ambulance_lat': c['ambulance_lat'],
                'ambulance_lng': c['ambulance_lng'],
                'assigned_hospital_id': c['assigned_hospital_id'],
                'final_score': c['final_score'],
                'distance_km': c['distance_km'],
                'eta_minutes': c['eta_minutes'],
            })
        conn.commit()

    print(f"\nTotal inserted: {len(cases_to_insert)} synthetic cases")
    print(f"({cases_per_condition} per condition × {len(CONDITIONS)} conditions)")
    print(f"Districts: {', '.join(d['name'] for d in DISTRICTS)}")

if __name__ == '__main__':
    generate()
