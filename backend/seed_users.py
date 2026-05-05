from app.db.database import SessionLocal
from app.db.models import User, Hospital
from app.core.security import hash_password

def seed_users():
    db = SessionLocal()
    try:
        users = [
            {
                "email": "admin@example.com",
                "password": "password123",
                "role": "admin",
                "hospital_id": None
            },
            {
                "email": "ambulance@example.com",
                "password": "password123",
                "role": "ambulance",
                "hospital_id": None
            },
            {
                "email": "hospital@example.com",
                "password": "password123",
                "role": "hospital",
                "hospital_id": db.query(Hospital.id).first()[0] if db.query(Hospital).first() else None
            }
        ]

        for u_data in users:
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            if existing:
                print(f"User {u_data['email']} already exists. Skipping.")
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
