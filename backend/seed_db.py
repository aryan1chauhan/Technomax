from app.db.database import SessionLocal
from app.db.models import Hospital, Availability
from datetime import datetime, timezone

db = SessionLocal()

hospitals = [
    {
        "name": "Civil Hospital Roorkee",
        "address": "Civil Lines, Roorkee, Uttarakhand 247667",
        "lat": 29.8601,
        "lng": 77.8868,
        "beds": 12, "icu": 3, "doctors": 6,
        "equipment": ["ecg", "ventilator", "xray", "blood_bank"],
        "accepting": True
    },
    {
        "name": "Himalayan Hospital",
        "address": "Haridwar Road, Roorkee, Uttarakhand 247667",
        "lat": 29.8450,
        "lng": 77.8950,
        "beds": 8, "icu": 2, "doctors": 4,
        "equipment": ["ecg", "defibrillator", "ventilator"],
        "accepting": True
    },
    {
        "name": "Max Care Hospital Haridwar",
        "address": "Jwalapur, Haridwar, Uttarakhand 249407",
        "lat": 29.9295,
        "lng": 78.1350,
        "beds": 20, "icu": 5, "doctors": 10,
        "equipment": ["ecg", "ventilator", "defibrillator", "xray", "icu", "blood_bank"],
        "accepting": True
    },
    {
        "name": "AIIMS Rishikesh",
        "address": "Virbhadra Road, Rishikesh, Uttarakhand 249203",
        "lat": 30.0689,
        "lng": 78.3001,
        "beds": 50, "icu": 15, "doctors": 30,
        "equipment": ["ecg", "ventilator", "defibrillator", "xray", "icu", "blood_bank"],
        "accepting": True
    },
]

for h_data in hospitals:
    existing = db.query(Hospital).filter(Hospital.name == h_data["name"]).first()
    if existing:
        print(f"Skipping {h_data['name']} — already exists")
        continue

    hospital = Hospital(
        name=h_data["name"],
        address=h_data["address"],
        lat=h_data["lat"],
        lng=h_data["lng"]
    )
    db.add(hospital)
    db.flush()

    availability = Availability(
        hospital_id=hospital.id,
        beds=h_data["beds"],
        icu=h_data["icu"],
        doctors=h_data["doctors"],
        equipment=h_data["equipment"],
        accepting=h_data["accepting"],
        updated_at=datetime.now(timezone.utc)
    )
    db.add(availability)
    print(f"Added {h_data['name']} (id={hospital.id})")

db.commit()
db.close()
print("\nDone! All Roorkee-area hospitals seeded.")
