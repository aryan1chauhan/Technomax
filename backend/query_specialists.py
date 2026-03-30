from app.db.database import engine
from sqlalchemy import text
import json

with engine.connect() as c:
    rows = c.execute(text("SELECT specialists FROM hospitals")).fetchall()

total = len(rows)
has_specialists = 0
non_empty = 0

for (spec,) in rows:
    if spec is not None:
        has_specialists += 1
        
        parsed = {}
        if isinstance(spec, dict):
            parsed = spec
        elif isinstance(spec, str):
            if spec not in ('{}', '""', "null", "", "{} "):
                try:
                    parsed = json.loads(spec)
                except:
                    pass
                
        if parsed:
            non_empty += 1

print(f"TOTAL: {total} | HAS_SPECIALISTS: {has_specialists} | NON_EMPTY: {non_empty}")
