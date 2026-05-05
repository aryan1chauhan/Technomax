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
        "district": "Roorkee",
        "beds": 10000, "icu": 10000, "doctors": 6,
        "equipment": ["ecg", "ventilator", "xray", "blood_bank"],
        "accepting": True
    },
    {
        "name": "Himalayan Hospital",
        "address": "Haridwar Road, Roorkee, Uttarakhand 247667",
        "lat": 29.8450,
        "lng": 77.8950,
        "district": "Roorkee",
        "beds": 10000, "icu": 10000, "doctors": 4,
        "equipment": ["ecg", "defibrillator", "ventilator"],
        "accepting": True
    },
    {
        "name": "Max Care Hospital Haridwar",
        "address": "Jwalapur, Haridwar, Uttarakhand 249407",
        "lat": 29.9295,
        "lng": 78.1350,
        "district": "Haridwar",
        "beds": 10000, "icu": 10000, "doctors": 10,
        "equipment": ["ecg", "ventilator", "defibrillator", "xray", "icu", "blood_bank"],
        "accepting": True
    },
    {
        "name": "AIIMS Rishikesh",
        "address": "Virbhadra Road, Rishikesh, Uttarakhand 249203",
        "lat": 30.0689,
        "lng": 78.3001,
        "district": "Rishikesh",
        "beds": 10000, "icu": 10000, "doctors": 30,
        "equipment": ["ecg", "ventilator", "defibrillator", "xray", "icu", "blood_bank"],
        "accepting": True
    },
]

for h_data in hospitals:
    existing = db.query(Hospital).filter(Hospital.name == h_data["name"]).first()
    if existing:
        # Update existing availability instead of skipping, to refresh bed counts
        avail = db.query(Availability).filter(Availability.hospital_id == existing.id).first()
        if avail:
            avail.beds = h_data["beds"]
            avail.icu = h_data["icu"]
            avail.updated_at = datetime.now(timezone.utc)
            print(f"Updated beds for {h_data['name']} to {h_data['beds']}")
        continue

    hospital = Hospital(
        name=h_data["name"],
        address=h_data["address"],
        lat=h_data["lat"],
        lng=h_data["lng"],
        district=h_data.get("district")
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
print("\nDone! All Roorkee-area hospitals seeded with high capacity.")
