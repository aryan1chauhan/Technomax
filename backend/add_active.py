import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.database_url)

def run():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE availabilities ADD COLUMN active_cases INT DEFAULT 0;"))
            conn.commit()
            print("Added active_cases.")
        except Exception as e:
            conn.rollback()
            print(f"Column active_cases probably exists: {e}")

if __name__ == "__main__":
    run()
