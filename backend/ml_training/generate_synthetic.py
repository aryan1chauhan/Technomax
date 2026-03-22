import os
import random
import math
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
DATABASE_URL = os.getenv('DATABASE_URL')

# All conditions with their required equipment
CONDITIONS = {
    'cardiac arrest':       {'severity': 3, 'equipment': ['defibrillator', 'ventilator'], 'needs': ['icu']},
    'stroke':               {'severity': 3, 'equipment': ['ct_scan'],                     'needs': ['icu']},
    'trauma':               {'severity': 3, 'equipment': ['blood_bank', 'ventilator'],     'needs': ['icu']},
    'severe trauma':        {'severity': 3, 'equipment': ['blood_bank', 'ventilator'],     'needs': ['icu']},
    'respiratory failure':  {'severity': 3, 'equipment': ['ventilator'],                   'needs': ['icu']},
    'head injury':          {'severity': 3, 'equipment': ['ct_scan'],                      'needs': ['icu']},
    'internal bleeding':    {'severity': 3, 'equipment': ['blood_bank'],                   'needs': ['icu']},
    'spinal injury':        {'severity': 3, 'equipment': ['ct_scan'],                      'needs': ['icu']},
    'chest injury':         {'severity': 3, 'equipment': ['ventilator', 'defibrillator'],  'needs': []},
    'severe bleeding':      {'severity': 3, 'equipment': ['blood_bank'],                   'needs': []},
    'burns':                {'severity': 2, 'equipment': ['blood_bank'],                   'needs': []},
    'anaphylaxis':          {'severity': 2, 'equipment': ['ventilator'],                   'needs': []},
    'kidney failure':       {'severity': 2, 'equipment': [],                               'needs': ['icu']},
    'pelvic injury':        {'severity': 2, 'equipment': ['blood_bank', 'ct_scan'],        'needs': []},
    'hypoglycemic crisis':  {'severity': 2, 'equipment': [],                               'needs': ['icu']},
    'fractures':            {'severity': 1, 'equipment': ['xray'],                         'needs': []},
    'soft tissue injury':   {'severity': 1, 'equipment': [],                               'needs': []},
    'facial injury':        {'severity': 1, 'equipment': [],                               'needs': []},
    'psychological trauma': {'severity': 1, 'equipment': [],                               'needs': []},
    'broken bone':          {'severity': 1, 'equipment': ['xray'],                         'needs': []},
}

# Roorkee area bounds
LAT_MIN, LAT_MAX = 29.82, 29.90
LNG_MIN, LNG_MAX = 77.85, 77.95

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

    # Load hospitals with their equipment
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT h.id, h.name, h.lat, h.lng, a.beds, a.icu, a.equipment "
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
            'beds': r[4], 'icu': r[5], 'equipment': eq
        })

    if not hospitals:
        print("No hospitals found in database!")
        return

    print(f"Found {len(hospitals)} hospitals:")
    for h in hospitals:
        print(f"  {h['id']}: {h['name']} — eq={h['equipment']}")

    cases_to_insert = []
    cases_per_condition = 25

    for condition, info in CONDITIONS.items():
        needed_eq = info['equipment']

        for _ in range(cases_per_condition):
            amb_lat = random.uniform(LAT_MIN, LAT_MAX)
            amb_lng = random.uniform(LNG_MIN, LNG_MAX)

            # Score hospitals for this case
            best_hospital = None
            best_score = -1

            for h in hospitals:
                if h['beds'] <= 0:
                    continue

                # Equipment match
                if needed_eq:
                    eq_match = sum(1 for e in needed_eq if e in h['equipment']) / len(needed_eq)
                else:
                    eq_match = 1.0

                # ICU check
                icu_match = 1.0
                if 'icu' in info['needs'] and h['icu'] <= 0:
                    icu_match = 0.3

                # Distance (closer = better)
                dist = haversine(amb_lat, amb_lng, h['lat'], h['lng'])
                dist_score = max(0, 1 - dist / 50)  # normalize within 50km

                # Weighted score
                score = (eq_match * 0.4) + (dist_score * 0.3) + (icu_match * 0.2) + (h['beds'] / 50 * 0.1)

                # Boost: conditions needing ct_scan → prefer hospitals with ct_scan
                if 'ct_scan' in needed_eq and 'ct_scan' in h['equipment']:
                    score += 0.3

                # Boost: conditions needing defibrillator → prefer those
                if 'defibrillator' in needed_eq and 'defibrillator' in h['equipment']:
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

    # Batch insert into cases table
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

    print(f"\nInserted {len(cases_to_insert)} synthetic cases")

if __name__ == '__main__':
    generate()
