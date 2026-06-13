"""
seed_hospitals_roorkee.py

Seeds / fixes hospital + availability data for hospitals in Roorkee, Rishikesh, and Haridwar.

What this does:
1. FIXES existing placeholder data (district = N/A, beds = 0, icu = 10000)
   for "Civil Hospital Roorkee", "Himalayan Hospital", "AIIMS Rishikesh", and "Max Care Hospital Haridwar"
   so they show real numbers in the admin "Hospital Network Availability" view.
2. ADDS three more real Roorkee-area hospitals:
   - IIT Roorkee Institute Hospital (campus health center)
   - Tulsi Hospital (Ganeshpur, Roorkee)
   - Roorkee Hospital (private, Ashok Nagar)

Run from the backend root:
    python seed_hospitals_roorkee.py
"""

from app.db.database import SessionLocal
from app.db.models import Hospital, Availability

SPECIALISTS_MAP = {
    "neurology": "neurologist",
    "neuro": "neurologist",
    "cardiology": "cardiologist",
    "cardiac": "cardiologist",
    "orthopaedics": "orthopedic",
    "orthopaedic": "orthopedic",
    "orthopedics": "orthopedic",
    "ortho": "orthopedic",
    "gynaecology": "gynecologist",
    "gynecologist": "gynecologist",
    "gynecology": "gynecologist",
    "obstetrics": "gynecologist",
    "general_surgery": "general_surgeon",
    "surgery": "general_surgeon",
    "pulmonology": "pulmonologist",
    "paediatrics": "pediatrician",
    "pediatrician": "pediatrician",
    "pediatrics": "pediatrician",
    "endocrinology": "endocrinologist",
    "psychiatry": "psychiatrist",
    "ent": "ent_specialist",
    "ophthalmology": "ophthalmologist",
    "gastroenterology": "gastroenterologist",
    "trauma": "general_surgeon",
    "emergency": "emergency_physician",
    "emergency_care": "emergency_physician"
}

def map_specialists(specs_list):
    res = {}
    for spec in specs_list:
        mapped = SPECIALISTS_MAP.get(spec.lower(), spec.lower())
        res[mapped] = 1
    return res


# Data: hospitals + their current availability snapshot
ROORKEE_HOSPITALS = [
    # --- EXISTING ENTRIES (fix placeholder data) ---------------------------
    {
        "name": "Civil Hospital Roorkee",
        "address": "Civil Lines, Roorkee, Uttarakhand 247667",
        "lat": 29.8606,
        "lng": 77.8930,
        "hospital_type": "both",          # stabilization + advanced
        "has_icu": True,
        "district": "Roorkee",
        "specialists": ["general_medicine", "orthopedics", "gynecology", "pediatrics", "surgery"],
        "availability": {
            "beds": 50,
            "icu": 8,
            "doctors": 15,
            "equipment": ["ECG", "VENTILATOR", "XRAY", "BLOOD_BANK", "DEFIBRILLATOR", "ICU"],
            "accepting": True,
        },
    },
    {
        "name": "Himalayan Hospital",
        "address": "Haridwar Road, Roorkee, Uttarakhand 247667",
        "lat": 29.8551,
        "lng": 77.8852,
        "hospital_type": "stabilization",
        "has_icu": True,
        "district": "Roorkee",
        "specialists": ["general_medicine", "emergency_care"],
        "availability": {
            "beds": 20,
            "icu": 3,
            "doctors": 4,
            "equipment": ["ECG", "DEFIBRILLATOR", "VENTILATOR"],
            "accepting": True,
        },
    },

    # --- EXISTING RISHIKESH & HARIDWAR ENTRIES (fix placeholder data) ------
    {
        "name": "Max Care Hospital Haridwar",
        "address": "Jwalapur, Haridwar, Uttarakhand 249407",
        "lat": 29.9295,
        "lng": 78.1350,
        "hospital_type": "both",
        "has_icu": True,
        "district": "Haridwar",
        "specialists": ["cardiology", "neurology", "surgery", "gynecology"],
        "availability": {
            "beds": 500,
            "icu": 50,
            "doctors": 10,
            "equipment": ["ECG", "VENTILATOR", "DEFIBRILLATOR", "XRAY", "ICU", "BLOOD_BANK"],
            "accepting": True,
        },
    },
    {
        "name": "AIIMS Rishikesh",
        "address": "Virbhadra Road, Rishikesh, Uttarakhand 249203",
        "lat": 30.0689,
        "lng": 78.3001,
        "hospital_type": "both",
        "has_icu": True,
        "district": "Rishikesh",
        "specialists": ["cardiology", "neurology", "surgery", "gynecology", "pediatrics", "emergency_care"],
        "availability": {
            "beds": 2000,
            "icu": 200,
            "doctors": 50,
            "equipment": ["ECG", "VENTILATOR", "DEFIBRILLATOR", "XRAY", "ICU", "BLOOD_BANK"],
            "accepting": True,
        },
    },

    # --- NEW ROORKEE HOSPITALS -----------------------------------------------
    {
        "name": "IIT Roorkee Institute Hospital",
        "address": "IIT Roorkee Campus, Roorkee, Uttarakhand 247667",
        "lat": 29.8654,
        "lng": 77.8965,
        "hospital_type": "stabilization",
        "has_icu": False,
        "district": "Roorkee",
        "specialists": ["general_medicine"],
        "availability": {
            "beds": 15,
            "icu": 0,
            "doctors": 5,
            "equipment": ["ECG", "XRAY", "BLOOD_BANK"],
            "accepting": True,
        },
    },
    {
        "name": "Tulsi Hospital",
        "address": "Ganeshpur, Haridwar Road, Roorkee, Uttarakhand 247667",
        "lat": 29.8252,
        "lng": 77.8704,
        "hospital_type": "stabilization",
        "has_icu": True,
        "district": "Roorkee",
        "specialists": ["general_medicine", "gynecology", "surgery"],
        "availability": {
            "beds": 25,
            "icu": 4,
            "doctors": 8,
            "equipment": ["ECG", "VENTILATOR", "XRAY", "DEFIBRILLATOR"],
            "accepting": True,
        },
    },
    {
        "name": "Roorkee Hospital",
        "address": "Building No 642, Near Labour Chowk, Ashoka Marg, Ashok Nagar, Roorkee, Uttarakhand 247667",
        "lat": 29.8580,
        "lng": 77.8800,
        "hospital_type": "advanced",
        "has_icu": True,
        "district": "Roorkee",
        "specialists": ["general_surgery", "orthopedics", "gynecology"],
        "availability": {
            "beds": 30,
            "icu": 5,
            "doctors": 10,
            "equipment": ["ECG", "VENTILATOR", "XRAY", "ICU", "DEFIBRILLATOR", "BLOOD_BANK"],
            "accepting": True,
        },
    },
]


def upsert_hospital(db, data: dict) -> Hospital:
    """Find a hospital by name, update it if it exists, otherwise create it."""
    hospital = db.query(Hospital).filter(Hospital.name == data["name"]).first()

    mapped_specs = map_specialists(data["specialists"])

    fields = {
        "name": data["name"],
        "address": data["address"],
        "lat": data["lat"],
        "lng": data["lng"],
        "hospital_type": data["hospital_type"],
        "has_icu": data["has_icu"],
        "district": data["district"],
        "specialists": mapped_specs,
    }

    if hospital:
        for key, value in fields.items():
            setattr(hospital, key, value)
        print(f"Updated hospital: {hospital.name}")
    else:
        hospital = Hospital(**fields)
        db.add(hospital)
        db.flush()  # get hospital.id before creating availability
        print(f"Created hospital: {hospital.name}")

    return hospital


def upsert_availability(db, hospital: Hospital, avail: dict) -> Availability:
    """Find availability by hospital_id, update it if it exists, otherwise create it."""
    record = db.query(Availability).filter(Availability.hospital_id == hospital.id).first()

    fields = {
        "hospital_id": hospital.id,
        "beds": avail["beds"],
        "icu": avail["icu"],
        "doctors": avail["doctors"],
        "equipment": avail["equipment"],
        "accepting": avail["accepting"],
        "specialists": hospital.specialists,
    }

    if record:
        for key, value in fields.items():
            setattr(record, key, value)
        print(f"  -> Updated availability for {hospital.name}")
    else:
        record = Availability(**fields)
        db.add(record)
        print(f"  -> Created availability for {hospital.name}")

    return record


def main():
    db = SessionLocal()
    try:
        for entry in ROORKEE_HOSPITALS:
            hospital = upsert_hospital(db, entry)
            upsert_availability(db, hospital, entry["availability"])

        db.commit()
        print(f"\nDone. {len(ROORKEE_HOSPITALS)} hospitals processed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
