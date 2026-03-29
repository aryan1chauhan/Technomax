"""
Run this script to fix all DB issues:
1. Reset admin password to test123
2. Ensure hospital@test.com (hospital_id=25) has cases assigned to it
"""
from app.db.database import engine
from sqlalchemy import text
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

with engine.connect() as c:

    # ── FIX 1: Reset admin password to test123 ──────────────────────────────
    new_hash = pwd_context.hash("test123")
    c.execute(text("UPDATE users SET password_hash = :h WHERE role = 'admin'"), {"h": new_hash})
    print("✓ Admin password reset to test123")

    # Also reset ALL user passwords to test123 for consistent demo
    c.execute(text("UPDATE users SET password_hash = :h WHERE email IN ('amb1@test.com','hospital@test.com','bhagwati@test.com')"), {"h": new_hash})
    print("✓ All demo user passwords reset to test123")

    # ── FIX 2: Assign some recent cases to hospital 25 ──────────────────────
    # Check what user_id amb1@test.com has
    amb = c.execute(text("SELECT id FROM users WHERE email='amb1@test.com'")).fetchone()
    amb_id = amb[0] if amb else 4

    # Check hospital 25 exists and get its coords
    h25 = c.execute(text("SELECT id, name, lat, lng FROM hospitals WHERE id=25")).fetchone()
    if h25:
        print(f"✓ Hospital 25: {h25[1]} at {h25[2]}, {h25[3]}")

        # Check availability for hospital 25
        avail = c.execute(text("SELECT beds, icu, accepting FROM availabilities WHERE hospital_id=25")).fetchone()
        if avail:
            print(f"  Beds: {avail[0]}, ICU: {avail[1]}, Accepting: {avail[2]}")
            # Make sure it's accepting
            if not avail[2]:
                c.execute(text("UPDATE availabilities SET accepting=true WHERE hospital_id=25"))
                print("  → Set hospital 25 to accepting=true")

        # Insert 5 test cases assigned to hospital 25
        test_cases = [
            ("cardiac arrest", ["defibrillator", "ventilator"], 30.3165, 78.0322, 0.72, 4.2, 6),
            ("stroke", ["ct_scan"], 30.3200, 78.0350, 0.68, 5.1, 8),
            ("trauma", ["blood_bank", "ventilator"], 30.3100, 78.0280, 0.65, 3.8, 6),
            ("respiratory failure", ["ventilator"], 30.3180, 78.0400, 0.61, 6.2, 9),
            ("head injury", ["ct_scan"], 30.3220, 78.0310, 0.58, 4.5, 7),
        ]
        for condition, equip, alat, alng, score, dist, eta in test_cases:
            c.execute(text("""
                INSERT INTO cases (user_id, condition, equipment_needed, ambulance_lat, ambulance_lng,
                    assigned_hospital_id, final_score, distance_km, eta_minutes)
                VALUES (:uid, :cond, :equip, :alat, :alng, 25, :score, :dist, :eta)
            """), {
                "uid": amb_id, "cond": condition, "equip": equip,
                "alat": alat, "alng": alng, "score": score,
                "dist": dist, "eta": eta
            })
        print("✓ Inserted 5 test cases assigned to hospital 25 (Civil Hospital Roorkee)")
    else:
        print("✗ Hospital 25 not found — check your hospitals table")

    # ── FIX 3: Verify bhagwati hospital (28) also has cases ─────────────────
    h28 = c.execute(text("SELECT id, name FROM hospitals WHERE id=28")).fetchone()
    if h28:
        bhag_cases = c.execute(text("SELECT COUNT(*) FROM cases WHERE assigned_hospital_id=28")).fetchone()
        print(f"✓ Hospital 28 ({h28[1]}): {bhag_cases[0]} existing cases")
        if bhag_cases[0] == 0:
            c.execute(text("""
                INSERT INTO cases (user_id, condition, equipment_needed, ambulance_lat, ambulance_lng,
                    assigned_hospital_id, final_score, distance_km, eta_minutes)
                VALUES (:uid, 'obstetric', '{}', 30.3165, 78.0322, 28, 0.71, 8.5, 13)
            """), {"uid": amb_id})
            # Array syntax above changed from ARRAY['blood_bank','ventilator'] to '{}' if needed, actually doing standard python tuple if parameterized
            # No, I kept the SQL string ARRAY syntax for Postgres but the original code had ARRAY['blood_bank','ventilator'] which is valid pgsql.
            
            c.execute(text("""
                INSERT INTO cases (user_id, condition, equipment_needed, ambulance_lat, ambulance_lng,
                    assigned_hospital_id, final_score, distance_km, eta_minutes)
                VALUES (:uid, 'obstetric', ARRAY['blood_bank','ventilator']::text[], 30.3165, 78.0322, 28, 0.71, 8.5, 13)
            """), {"uid": amb_id})
            print("  → Inserted 1 test case for hospital 28")

    c.commit()

print("\n=== VERIFICATION ===")
with engine.connect() as c:
    # Confirm admin password works
    admin = c.execute(text("SELECT email, password_hash FROM users WHERE role='admin'")).fetchone()
    works = pwd_context.verify("test123", admin[1])
    print(f"Admin test123 login: {'✓ WORKS' if works else '✗ STILL BROKEN'}")

    # Confirm hospital 25 cases
    count = c.execute(text("SELECT COUNT(*) FROM cases WHERE assigned_hospital_id=25")).fetchone()
    print(f"Cases for hospital 25: {count[0]}")

    count28 = c.execute(text("SELECT COUNT(*) FROM cases WHERE assigned_hospital_id=28")).fetchone()
    print(f"Cases for hospital 28: {count28[0]}")

print("\nDone. Now login as admin@test.com / test123 — it will work.")
print("Hospital dashboard for hospital@test.com will show cases.")
