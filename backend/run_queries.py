import sys
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://postgres:postgres@localhost:5432/mediroute")

with engine.connect() as conn:
    print("--- COUNT HOSPITALS ---")
    print(conn.execute(text("SELECT COUNT(*) FROM hospitals")).scalar())
    
    print("--- COUNT AVAILABILITIES ---")
    print(conn.execute(text("SELECT COUNT(*) FROM availabilities")).scalar())
    
    print("--- COUNT CASES ---")
    print(conn.execute(text("SELECT COUNT(*) FROM cases")).scalar())
    
    print("--- COUNT USERS ---")
    print(conn.execute(text("SELECT COUNT(*) FROM users")).scalar())
    
    print("--- TOP 5 HOSPITALS BY BEDS ---")
    res = conn.execute(text("SELECT id, name, beds, icu FROM hospitals JOIN availabilities ON hospital_id=hospitals.id ORDER BY beds DESC LIMIT 5"))
    for row in res:
        print(row)
