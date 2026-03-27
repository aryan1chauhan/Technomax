from app.db.database import SessionLocal
from app.db.models import User

db = SessionLocal()
admin = db.query(User).filter(User.email=="admin@test.com").first()

if not admin:
    admin = User(
        email="admin@test.com", 
        password_hash="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW", 
        role="admin"
    )
    db.add(admin)
else:
    admin.role = "admin"
    admin.password_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

db.commit()
print("Admin user successfully ensured in DB!")
