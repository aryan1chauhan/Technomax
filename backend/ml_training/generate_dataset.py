import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import math

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
DATABASE_URL = os.getenv('DATABASE_URL')

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Maps conditions to the equipment/capabilities a hospital needs
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
    'fractures':           [],
    'soft tissue injury':  [],
    'facial injury':       [],
    'psychological trauma':[],
    'severe bleeding':     ['blood_bank'],
    'broken bone':         [],
    'mild allergic reaction': [],
}

CONDITION_SEVERITY_MAP = {
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
    'other': 1,
}

def generate_dataset():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in .env")
        return
        
    engine = create_engine(DATABASE_URL)
    
    # Read cases and hospitals
    try:
        cases_df = pd.read_sql("SELECT * FROM cases", engine)
        hospitals_df = pd.read_sql("""
            SELECT h.id, h.name, h.lat, h.lng,
                   a.beds, a.icu, a.doctors, 
                   a.equipment, a.accepting
            FROM hospitals h
            JOIN availabilities a ON a.hospital_id = h.id
        """, engine)
    except Exception as e:
        print(f"Error reading from database: {e}")
        return
        
    training_data = []
    
    for _, case in cases_df.iterrows():
        # Needed equipment (could be comma separated or array depending on DB)
        needed_eq = case.get('equipment_needed', [])
        if isinstance(needed_eq, list):
            needed_items = [e.lower() for e in needed_eq if e]
        elif isinstance(needed_eq, str):
            needed_items = [e.strip().lower() 
                           for e in needed_eq.strip('{}').split(',') 
                           if e.strip()]
        else:
            needed_items = []
            
        case_lat = float(case.get('ambulance_lat', 0.0) or 0.0)
        case_lng = float(case.get('ambulance_lng', 0.0) or 0.0)
        condition_str = str(case.get('condition', '')).lower()
        condition_severity = CONDITION_SEVERITY_MAP.get(condition_str, 1)
        speciality_needed = CONDITION_SPECIALITY_MAP.get(condition_str, [])
        assigned_hosp_id = case.get('assigned_hospital_id')
        
        for _, hospital in hospitals_df.iterrows():
            # Hospital availability and equipment
            hosp_eq = hospital.get('equipment', [])
            if isinstance(hosp_eq, list):
                avail_items = [e.lower() for e in hosp_eq if e]
            elif isinstance(hosp_eq, str):
                avail_items = [e.strip().lower() 
                              for e in hosp_eq.strip('{}').split(',') 
                              if e.strip()]
            else:
                avail_items = []
                
            # Equipment match
            if len(needed_items) > 0:
                match_count = sum(1 for item in needed_items if item in avail_items)
                equipment_match = match_count / len(needed_items)
            else:
                equipment_match = 1.0
                
            hosp_lat = float(hospital.get('lat', 0.0) or 0.0)
            hosp_lng = float(hospital.get('lng', 0.0) or 0.0)
                
            distance_km = haversine_distance(case_lat, case_lng, hosp_lat, hosp_lng)
            
            was_selected = 1 if assigned_hosp_id == hospital.get('id') else 0
            
            # Speciality match: does hospital have the equipment this condition needs?
            if speciality_needed:
                spec_match_count = sum(1 for item in speciality_needed if item in avail_items)
                speciality_match = spec_match_count / len(speciality_needed)
            else:
                speciality_match = 1.0

            # Hospital load proxy: beds / 30, clamped to [0, 1]
            beds_val = hospital.get('beds', 0) or 0
            hospital_load = min(beds_val / 30, 1.0)

            training_data.append({
                'distance_km': distance_km,
                'beds': beds_val,
                'icu': hospital.get('icu', 0),
                'equipment_match': equipment_match,
                'severity_weight': condition_severity,
                'has_ventilator': 1 if 'ventilator' in avail_items else 0,
                'has_defibrillator': 1 if 'defibrillator' in avail_items else 0,
                'has_ct_scan': 1 if 'ct_scan' in avail_items else 0,
                'has_blood_bank': 1 if 'blood_bank' in avail_items else 0,
                'has_icu_equipment': 1 if 'icu' in avail_items else 0,
                'doctor_count': hospital.get('doctors', 0),
                'accepting': 1 if hospital.get('accepting', True) else 0,
                'speciality_match': speciality_match,
                'hospital_load': hospital_load,
                'condition_severity': condition_severity,
                'was_selected': was_selected
            })
            
    df = pd.DataFrame(training_data)
    
    output_path = os.path.join(os.path.dirname(__file__), 'training_data.csv')
    df.to_csv(output_path, index=False)
    
    print(f"Generated {len(df)} training samples")

if __name__ == '__main__':
    generate_dataset()
