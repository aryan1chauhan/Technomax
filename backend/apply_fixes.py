import os
import json
import random
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.database_url)

def run():
    print("1. ALTER TABLE: adding ot_available and specialists to availabilities")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE availabilities ADD COLUMN ot_available INT DEFAULT 0;"))
            conn.commit()
            print("Added ot_available.")
        except Exception as e:
            conn.rollback()
            print(f"Column ot_available probably exists: {e}")

    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE availabilities ADD COLUMN specialists JSONB DEFAULT '{}'::jsonb;"))
            conn.commit()
            print("Added specialists.")
        except Exception as e:
            conn.rollback()
            print(f"Column specialists probably exists: {e}")

    print("2. UPDATE cases: normalizing condition strings in cases table")
    with engine.connect() as conn:
        conn.execute(text("UPDATE cases SET condition = 'cardiac arrest' WHERE condition = 'cardiac_arrest';"))
        conn.execute(text("UPDATE cases SET condition = 'kidney failure' WHERE condition = 'kidney_failure';"))
        conn.execute(text("UPDATE cases SET condition = 'spinal injury' WHERE condition = 'spinal_injury';"))
        conn.execute(text("UPDATE cases SET condition = 'allergic reaction' WHERE condition = 'allergic_reaction';"))
        conn.execute(text("UPDATE cases SET condition = 'chest pain' WHERE condition = 'chest_pain';"))
        conn.execute(text("UPDATE cases SET condition = 'heart failure' WHERE condition = 'heart_failure';"))
        conn.execute(text("UPDATE cases SET condition = 'liver failure' WHERE condition = 'liver_failure';"))
        conn.commit()
        print("Conditions normalized.")

    print("3. SEEDING ot_available and specialists in hospital data")
    with engine.connect() as conn:
        hospitals = conn.execute(text("SELECT id, hospital_id, beds, equipment FROM availabilities;")).fetchall()
        
        for h in hospitals:
            avail_id, h_id, beds, equipment = h
            
            if beds > 200:
                ot_available = random.randint(2, 6)
            elif beds > 50:
                ot_available = random.randint(1, 4)
            else:
                ot_available = random.randint(0, 2)
            
            specs = {}
            if equipment:
                if "defibrillator" in equipment:
                    specs["cardiologist"] = random.randint(1, 3)
                if "ct_scan" in equipment:
                    specs["neurologist"] = random.randint(1, 2)
                if "blood_bank" in equipment and "ventilator" in equipment:
                    specs["general_surgeon"] = random.randint(1, 4)
            
            if beds > 100:
                specs["gynecologist"] = random.randint(1, 2)
                specs["nephrologist"] = random.randint(0, 2)
                specs["pulmonologist"] = random.randint(1, 2)
                specs["orthopedic"] = random.randint(1, 3)
                specs["pediatrician"] = random.randint(1, 4)
                specs["plastic_surgeon"] = random.randint(0, 1)

            spec_json = json.dumps(specs)
            
            conn.execute(
                text("UPDATE availabilities SET ot_available = :ot, specialists = :specs WHERE id = :id"),
                {"ot": ot_available, "specs": spec_json, "id": avail_id}
            )
        
        conn.commit()
        print("Data seeded successfully.")

if __name__ == "__main__":
    run()
