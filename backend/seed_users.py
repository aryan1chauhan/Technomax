from app.db.database import SessionLocal
from app.db.models import User, Hospital
from app.core.security import hash_password

def seed_users():
    db = SessionLocal()
    try:
        civil_id = None
        himalayan_id = None
        first_hosp = db.query(Hospital).first()
        first_hosp_id = first_hosp.id if first_hosp else None

        civil_hosp = db.query(Hospital).filter(Hospital.name.like("%Civil Hospital%")).first()
        civil_id = civil_hosp.id if civil_hosp else first_hosp_id

        himalayan_hosp = db.query(Hospital).filter(Hospital.name.like("%Himalayan%")).first()
        himalayan_id = himalayan_hosp.id if himalayan_hosp else first_hosp_id

        users = [
            {
                "email": "admin@test.com",
                "password": "test123",
                "role": "admin",
                "hospital_id": None
            },
            {
                "email": "amb1@test.com",
                "password": "test123",
                "role": "ambulance",
                "hospital_id": None
            },
            {
                "email": "hospital@test.com",
                "password": "test123",
                "role": "hospital",
                "hospital_id": civil_id
            },
            {
                "email": "bhagwati@test.com",
                "password": "test123",
                "role": "hospital",
                "hospital_id": himalayan_id
            }
        ]

        for u_data in users:
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            if existing:
                existing.password_hash = hash_password(u_data["password"])
                existing.hospital_id = u_data["hospital_id"]
                print(f"Updated user: {u_data['email']}")
                continue
            
            new_user = User(
                email=u_data["email"],
                password_hash=hash_password(u_data["password"]),
                role=u_data["role"],
                hospital_id=u_data["hospital_id"]
            )
            db.add(new_user)
            print(f"Added user: {u_data['email']} ({u_data['role']})")
        
        db.commit()
    except Exception as e:
        print(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
