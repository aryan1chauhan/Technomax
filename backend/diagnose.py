from app.db.database import engine
from sqlalchemy import text

with engine.connect() as c:
    print("=== USERS ===")
    rows = c.execute(text("SELECT id, email, role, hospital_id FROM users ORDER BY id")).fetchall()
    for r in rows:
         print(r)

    print("\n=== RECENT CASES ===")
    rows = c.execute(text("SELECT id, condition, assigned_hospital_id, final_score, distance_km FROM cases ORDER BY id DESC LIMIT 5")).fetchall()
    for r in rows:
         print(r)

    print("\n=== HOSPITAL USERS ===")
    rows = c.execute(text("SELECT u.email, u.hospital_id, h.name FROM users u LEFT JOIN hospitals h ON h.id = u.hospital_id WHERE u.role = 'hospital'")).fetchall()
    for r in rows:
         print(r)

    print("\n=== ADMIN USER CHECK ===")
    rows = c.execute(text("SELECT id, email, role, password_hash FROM users WHERE role = 'admin'")).fetchall()
    for r in rows:
         print(r)
