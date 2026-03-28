import os
import random
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.database_url)

def run():
    print("Giving active_cases real variance...")
    with engine.connect() as conn:
        try:
            hospitals = conn.execute(text("SELECT id FROM availabilities;")).fetchall()
            for h in hospitals:
                active_cases = random.randint(0, 14)
                conn.execute(
                    text("UPDATE availabilities SET active_cases = :val WHERE id = :id"),
                    {"val": active_cases, "id": h.id}
                )
            conn.commit()
            print("Successfully updated active_cases.")
        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    run()
