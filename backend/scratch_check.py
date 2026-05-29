import asyncio
from app.db.database import SessionLocal
from app.db.models import Hospital, Availability
from app.engine.ml_scorer import rank_hospitals

async def main():
    db = SessionLocal()
    rows = db.query(Hospital, Availability).join(Availability, Availability.hospital_id == Hospital.id).all()
    hospitals_list = []
    for h, a in rows:
        hospitals_list.append({
            'id': h.id,
            'name': h.name,
            'latitude': h.lat,
            'longitude': h.lng,
            'available_beds': a.beds,
            'icu_beds': a.icu,
            'equipment': a.equipment,
            'accepting': a.accepting,
            'specialist_count': a.doctors,
            'specialists': a.specialists,
        })
    db.close()

    # 1. Test Cardiac Case
    print("\n--- TEST: CARDIAC ARREST CASE (Critical, ECG + Defibrillator needed) ---")
    cardiac_results = await rank_hospitals(
        hospitals_list,
        ambulance_lat=29.8700,
        ambulance_lon=77.8800,
        required_equipment=['ecg', 'defibrillator'],
        condition='cardiac_arrest',
        severity_score=9
    )
    for i, h in enumerate(cardiac_results[:3], 1):
        score_breakdown = h.get('score_breakdown', {})
        s_treatment = score_breakdown.get('S_treatment')
        print(f"Rank {i}: {h['name']}")
        print(f"  Final Score: {h['score']:.4f} | S_treatment (Specialist Match): {s_treatment}")
        print(f"  Equipment: {h['equipment']}")
        print(f"  Specialists: {h['specialists']}")

    # 2. Test Stroke Case
    print("\n--- TEST: STROKE CASE (Critical, CT Scan needed) ---")
    stroke_results = await rank_hospitals(
        hospitals_list,
        ambulance_lat=29.8700,
        ambulance_lon=77.8800,
        required_equipment=['ct_scan'],
        condition='stroke',
        severity_score=8
    )
    for i, h in enumerate(stroke_results[:3], 1):
        score_breakdown = h.get('score_breakdown', {})
        s_treatment = score_breakdown.get('S_treatment')
        print(f"Rank {i}: {h['name']}")
        print(f"  Final Score: {h['score']:.4f} | S_treatment (Specialist Match): {s_treatment}")
        print(f"  Equipment: {h['equipment']}")
        print(f"  Specialists: {h['specialists']}")

if __name__ == "__main__":
    asyncio.run(main())
