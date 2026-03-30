from app.db.database import engine
from sqlalchemy import text

with engine.connect() as c:
    c.execute(text(
        "ALTER TABLE availabilities ADD COLUMN IF NOT EXISTS specialists JSONB DEFAULT '{}'"
    ))
    c.commit()
    print("✓ specialists column added to availabilities")
