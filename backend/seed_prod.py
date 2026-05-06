import os
from app.db.database import SessionLocal
from app.db.models import User, Hospital, Availability
from app.core.security import hash_password
from datetime import datetime, timezone

def seed_production():
    db = SessionLocal()
    print("Starting production seed...")
    
    try:
        # 1. Seed Hospitals
        hospitals_data = [
            {
                "name": "Civil Hospital Roorkee",
                "address": "Civil Lines, Roorkee, Uttarakhand 247667",
                "lat": 29.8601, "lng": 77.8868, "district": "Roorkee",
                "beds": 1000, "icu": 100, "doctors": 20,
                "equipment": ["ecg", "ventilator", "xray", "blood_bank"],
                "accepting": True
            },
            {
                "name": "Himalayan Hospital",
                "address": "Haridwar Road, Roorkee, Uttarakhand 247667",
                "lat": 29.8450, "lng": 77.8950, "district": "Roorkee",
                "beds": 800, "icu": 80, "doctors": 15,
                "equipment": ["ecg", "defibrillator", "ventilator"],
                "accepting": True
            },
            {
                "name": "Max Care Hospital Haridwar",
                "address": "Jwalapur, Haridwar, Uttarakhand 249407",
                "lat": 29.9295, "lng": 78.1350, "district": "Haridwar",
                "beds": 500, "icu": 50, "doctors": 10,
                "equipment": ["ecg", "ventilator", "defibrillator", "xray", "icu", "blood_bank"],
                "accepting": True
            },
            {
                "name": "AIIMS Rishikesh",
                "address": "Virbhadra Road, Rishikesh, Uttarakhand 249203",
                "lat": 30.0689, "lng": 78.3001, "district": "Rishikesh",
                "beds": 2000, "icu": 200, "doctors": 50,
                "equipment": ["ecg", "ventilator", "defibrillator", "xray", "icu", "blood_bank"],
                "accepting": True
            },
        ]

        hospital_map = {}
        for h_data in hospitals_data:
            h = db.query(Hospital).filter(Hospital.name == h_data["name"]).first()
            if not h:
                h = Hospital(
                    name=h_data["name"],
                    address=h_data["address"],
                    lat=h_data["lat"],
                    lng=h_data["lng"],
                    district=h_data["district"]
                )
                db.add(h)
                db.flush()
                
                avail = Availability(
                    hospital_id=h.id,
                    beds=h_data["beds"],
                    icu=h_data["icu"],
                    doctors=h_data["doctors"],
                    equipment=h_data["equipment"],
                    accepting=h_data["accepting"],
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(avail)
                print(f"Created hospital: {h.name}")
            else:
                print(f"Hospital {h.name} exists.")
            hospital_map[h.name] = h.id

        # 2. Seed Users
        test_password = hash_password("test123")
        users_data = [
            {"email": "admin@test.com", "role": "admin", "hospital": None},
            {"email": "amb1@test.com", "role": "ambulance", "hospital": None},
            {"email": "hospital@test.com", "role": "hospital", "hospital": "Civil Hospital Roorkee"},
            {"email": "bhagwati@test.com", "role": "hospital", "hospital": "Himalayan Hospital"},
        ]

        for u_data in users_data:
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            h_id = hospital_map.get(u_data["hospital"]) if u_data["hospital"] else None
            
            if not existing:
                user = User(
                    email=u_data["email"],
                    password_hash=test_password,
                    role=u_data["role"],
                    hospital_id=h_id
                )
                db.add(user)
                print(f"Created user: {u_data['email']} ({u_data['role']})")
            else:
                # Update existing user to have the correct password and hospital_id for safety
                existing.password_hash = test_password
                existing.hospital_id = h_id
                print(f"Updated user: {u_data['email']}")

        db.commit()
        print("\nProduction seed finished successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error during seed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_production()
