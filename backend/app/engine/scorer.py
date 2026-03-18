from app.engine.haversine import calculate_distance

def score_hospital(hospital: dict, equipment_needed: list[str], distance_km: float) -> dict | None:
    if not hospital.get("accepting", True) or hospital.get("beds", 0) == 0:
        return None

    availability = min(hospital.get("beds", 0) / 10, 1.0)
    distance_score = 1 / (1 + distance_km)
    
    needed = set(equipment_needed)
    available = set(hospital.get("equipment", []))
    
    if not needed:
        equipment_score = 1.0
    else:
        equipment_score = len(needed & available) / len(needed)
        
    final_score = (availability * 0.40) + (distance_score * 0.35) + (equipment_score * 0.25)
    
    equipment_matched = list(needed & available)
    equipment_missing = list(needed - available)
    
    eta_minutes = round((distance_km / 40) * 60)
    
    return {
        "final_score": round(final_score, 4),
        "distance_km": distance_km,
        "eta_minutes": eta_minutes,
        "equipment_matched": equipment_matched,
        "equipment_missing": equipment_missing
    }


def find_best_hospital(hospitals: list[dict], equipment_needed: list[str], ambulance_lat: float, ambulance_lng: float) -> dict | None:
    valid_hospitals = []
    
    for hospital in hospitals:
        distance_km = calculate_distance(
            ambulance_lat, ambulance_lng, 
            hospital["lat"], hospital["lng"]
        )
        
        score_data = score_hospital(hospital, equipment_needed, distance_km)
        
        if score_data is not None:
            merged_hospital = {**hospital, **score_data}
            valid_hospitals.append(merged_hospital)
            
    if not valid_hospitals:
        return None
        
    # Sort descending by final_score
    valid_hospitals.sort(key=lambda x: x["final_score"], reverse=True)
    
    return valid_hospitals[0]
