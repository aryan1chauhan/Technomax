from app.db.database import SessionLocal
from app.db.models import User, Hospital
from app.core.security import hash_password

db = SessionLocal()
try:
    hospital = db.query(Hospital).first()
    hospital_id = hospital.id if hospital else None
    print(f"First hospital: id={hospital_id}")

    users_to_seed = [
        {"email": "admin@test.com",    "password": "test123",     "role": "admin",     "hospital_id": None},
        {"email": "amb1@test.com",     "password": "test123",     "role": "ambulance", "hospital_id": None},
        {"email": "hospital@test.com", "password": "test123",     "role": "hospital",  "hospital_id": hospital_id},
        {"email": "admin@example.com", "password": "password123", "role": "admin",     "hospital_id": None},
    ]

    for u in users_to_seed:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if existing:
            print(f"Already exists: {u['email']}")
            continue
        new_user = User(
            email=u["email"],
            password_hash=hash_password(u["password"]),
            role=u["role"],
            hospital_id=u["hospital_id"]
        )
        db.add(new_user)
        print(f"Added: {u['email']} ({u['role']})")

    db.commit()
    print("Done.")
except Exception as e:
    db.rollback()
    print(f"ERROR: {e}")
finally:
    db.close()
