from app.db.database import engine
from sqlalchemy import text

with engine.connect() as c:
    row = c.execute(text("""
        SELECT a.specialists 
        FROM availabilities a
        JOIN hospitals h ON h.id = a.hospital_id
        WHERE h.name ILIKE '%civil%roorkee%'
        LIMIT 1
    """)).fetchone()
    print(row)
