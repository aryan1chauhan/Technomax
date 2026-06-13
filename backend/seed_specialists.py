from app.db.database import engine
from sqlalchemy import text
import json

specialist_profiles = {
    "large":  {"cardiologist": 2, "neurologist": 2, "general_surgeon": 3,
               "orthopedic": 2, "gynecologist": 2, "nephrologist": 1,
               "pulmonologist": 1, "emergency_physician": 3, "endocrinologist": 1},
    "medium": {"general_surgeon": 2, "orthopedic": 1,
               "gynecologist": 1, "emergency_physician": 2, "neurologist": 1},
    "small":  {"emergency_physician": 1}
}

with engine.connect() as c:
    rows = c.execute(text("""
        SELECT a.id, a.beds 
        FROM availabilities a
        JOIN (
            SELECT hospital_id, MAX(updated_at) as max_ts
            FROM availabilities GROUP BY hospital_id
        ) latest ON a.hospital_id = latest.hospital_id 
               AND a.updated_at = latest.max_ts
    """)).fetchall()

    counts = {"large": 0, "medium": 0, "small": 0}

    for (avail_id, beds) in rows:
        if beds >= 100:
            tier = "large"
        elif beds >= 40:
            tier = "medium"
        else:
            tier = "small"
        
        c.execute(text(
            "UPDATE availabilities SET specialists = cast(:spec as jsonb) WHERE id = :id"
        ), {"spec": json.dumps(specialist_profiles[tier]), "id": avail_id})
        counts[tier] += 1

    c.commit()
    print(f"✓ Seeded: {counts}")

    
