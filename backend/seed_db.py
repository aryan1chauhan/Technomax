"""
seed_db.py — Real Roorkee Hospital Data
Seeds the MediRoute database with actual hospitals from Roorkee, Uttarakhand.
Data sourced from Google Maps — coordinates, specialties, ratings, and bed counts are real or
realistically estimated based on facility size and type.

Usage:
    python seed_db.py
"""

from app.db.database import SessionLocal
from app.db.models import Hospital, Availability
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Master hospital dataset — 30 real Roorkee facilities
# ---------------------------------------------------------------------------

HOSPITALS = [
    # ── MULTISPECIALITY / GENERAL ──────────────────────────────────────────
    {
        "name": "Arogya Super Speciality Health Care",
        "address": "Durga Chowk, Nehru Stadium, Veer Bhawan Nagar, Roorkee",
        "latitude": 29.8721,
        "longitude": 77.8834,
        "phone": "+91 96904 80483",
        "rating": 4.9,
        "total_beds": 30,
        "available_beds": 12,
        "icu_beds": 4,
        "specialists": ["neurology", "ent", "cardiology", "gastroenterology"],
        "equipment": ["ecg", "ultrasound", "xray", "nebulizer"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Best neurology + ENT in Roorkee. Highly rated.",
    },
    {
        "name": "SRM Medicity Hospital",
        "address": "Haridwar Rd, Sherpur, Roorkee",
        "latitude": 29.8804,
        "longitude": 77.9133,
        "phone": "+91 98374 43335",
        "rating": 4.5,
        "total_beds": 60,
        "available_beds": 22,
        "icu_beds": 8,
        "specialists": [
            "cardiology",
            "neurology",
            "gastroenterology",
            "endocrinology",
            "psychiatry",
        ],
        "equipment": ["ecg", "ultrasound", "xray", "ct_scan", "icu", "ventilator"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Diabetes, thyroid, neuro, gastro specialist hospital.",
    },
    {
        "name": "VinayVishal HealthCare",
        "address": "Gandhi Nagar, Roorkee",
        "latitude": 29.8670,
        "longitude": 77.8772,
        "phone": "+91 70785 99991",
        "rating": 3.7,
        "total_beds": 80,
        "available_beds": 30,
        "icu_beds": 6,
        "specialists": [
            "general_medicine",
            "gynaecology",
            "surgery",
            "paediatrics",
        ],
        "equipment": ["ecg", "ultrasound", "xray", "icu"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Large multi-doctor hospital. Mixed reviews.",
    },
    {
        "name": "Arogyam Hospital",
        "address": "Karaundi, Bhagwanpur, Roorkee (15 km)",
        "latitude": 29.9256,
        "longitude": 77.8291,
        "phone": "+91 75339 20244",
        "rating": 4.8,
        "total_beds": 150,
        "available_beds": 55,
        "icu_beds": 20,
        "specialists": [
            "general_medicine",
            "surgery",
            "gynaecology",
            "orthopaedics",
            "cardiology",
            "paediatrics",
        ],
        "equipment": ["ecg", "ultrasound", "xray", "ct_scan", "mri", "icu", "ventilator"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Medical college & hospital. Largest facility near Roorkee.",
    },

    # ── GYNAECOLOGY / MATERNITY ─────────────────────────────────────────────
    {
        "name": "Medwin Hospital",
        "address": "Azad Nagar Puliya, Rajendra Nagar, Roorkee",
        "latitude": 29.8683,
        "longitude": 77.8758,
        "phone": "+91 93685 00139",
        "rating": 4.8,
        "total_beds": 20,
        "available_beds": 8,
        "icu_beds": 2,
        "specialists": ["gynaecology", "obstetrics", "general_medicine"],
        "equipment": ["ultrasound", "ecg", "xray"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Best gynaecologist hospital in Roorkee per local reviews.",
    },
    {
        "name": "Rishi Hospital",
        "address": "612, Ashok Marg, Ramnagar, Roorkee",
        "latitude": 29.8756,
        "longitude": 77.8719,
        "phone": "+91 63991 22850",
        "rating": 4.5,
        "total_beds": 25,
        "available_beds": 10,
        "icu_beds": 3,
        "specialists": ["gynaecology", "obstetrics", "emergency"],
        "equipment": ["ultrasound", "ecg", "xray", "nicu"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Dr. Sonali Shahi Saini — well-reviewed gynaecologist.",
    },
    {
        "name": "Roorkee Hospital",
        "address": "642, Labour Chowk, Ramnagar, Roorkee",
        "latitude": 29.8757,
        "longitude": 77.8721,
        "phone": "+91 94111 95083",
        "rating": 4.7,
        "total_beds": 35,
        "available_beds": 14,
        "icu_beds": 4,
        "specialists": ["general_medicine", "gynaecology", "obstetrics", "surgery"],
        "equipment": ["ultrasound", "ecg", "xray", "icu"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "General + maternity. Affordable treatment.",
    },
    {
        "name": "Raj Hospital Maternity & Orthopaedic",
        "address": "575 Purwawali, Railway Station Rd, Ganesh Pur, Roorkee",
        "latitude": 29.8553,
        "longitude": 77.8771,
        "phone": "+91 91197 69725",
        "rating": 4.7,
        "total_beds": 20,
        "available_beds": 7,
        "icu_beds": 2,
        "specialists": ["gynaecology", "obstetrics", "orthopaedics"],
        "equipment": ["ultrasound", "xray", "ecg"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Maternity + orthopaedic combo. Very reasonable fees.",
    },
    {
        "name": "Abhilasha Eye & Maternity Hospital",
        "address": "Railway Station Rd, Bhagirath Kunj, Roorkee",
        "latitude": 29.8565,
        "longitude": 77.8793,
        "phone": "+91 1332 272 586",
        "rating": 4.7,
        "total_beds": 30,
        "available_beds": 11,
        "icu_beds": 2,
        "specialists": ["ophthalmology", "gynaecology", "obstetrics"],
        "equipment": ["ultrasound", "xray", "slit_lamp", "phaco_machine"],
        "is_24_7": False,
        "accepts_ayushman": True,
        "notes": "Eye surgery + maternity. Dr. C.S. Grover — cataract specialist.",
    },
    {
        "name": "VELLIANGIRI Heart & Multispeciality Hospital",
        "address": "NH 58, near Solani Bridge, World Bank Colony, Roorkee",
        "latitude": 29.8767,
        "longitude": 77.8982,
        "phone": None,
        "rating": 4.1,
        "total_beds": 40,
        "available_beds": 16,
        "icu_beds": 6,
        "specialists": ["cardiology", "gynaecology", "obstetrics", "general_medicine"],
        "equipment": ["ecg", "echo", "ultrasound", "xray", "icu"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Dr. Neha Saini — highly rated gynaecologist. Dr. Arpit Saini — cardiologist.",
    },

    # ── CARDIOLOGY ──────────────────────────────────────────────────────────
    {
        "name": "Bhargava Nursing Home",
        "address": "Railway Station Rd, Bhagirath Kunj, Roorkee",
        "latitude": 29.8568,
        "longitude": 77.8797,
        "phone": "+91 72539 25756",
        "rating": 4.2,
        "total_beds": 15,
        "available_beds": 6,
        "icu_beds": 3,
        "specialists": ["cardiology", "general_medicine"],
        "equipment": ["ecg", "echo", "xray", "icu"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Dr. Ajay Bhargava — renowned cardiologist. Saved many cardiac emergencies.",
    },
    {
        "name": "Deepak Savitri Global Hospital & Heart Care",
        "address": "Civil Lines, Roorkee",
        "latitude": 29.8700,
        "longitude": 77.8870,
        "phone": None,
        "rating": 4.6,
        "total_beds": 35,
        "available_beds": 13,
        "icu_beds": 8,
        "specialists": ["cardiology", "cardiac_surgery", "general_medicine"],
        "equipment": ["ecg", "echo", "cath_lab", "icu", "ventilator", "xray"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Dedicated cardiac hospital. Has cath lab for interventional cardiology.",
    },
    {
        "name": "Vardhman Hospital",
        "address": "33, Jadugar Road, Civil Lines, Roorkee",
        "latitude": 29.8677,
        "longitude": 77.8868,
        "phone": "+91 97590 05591",
        "rating": 3.9,
        "total_beds": 40,
        "available_beds": 15,
        "icu_beds": 5,
        "specialists": ["cardiology", "general_medicine", "surgery"],
        "equipment": ["ecg", "echo", "ultrasound", "xray", "icu"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Dr. Ravi Jain — well-known cardiologist in Roorkee.",
    },

    # ── GENERAL SURGERY ─────────────────────────────────────────────────────
    {
        "name": "Dev Nursing Home",
        "address": "672/1, Dehradun Rd, BSM Degree College, Ganesh Pur, Roorkee",
        "latitude": 29.8628,
        "longitude": 77.8786,
        "phone": "+91 97590 05900",
        "rating": 4.8,
        "total_beds": 25,
        "available_beds": 10,
        "icu_beds": 3,
        "specialists": ["general_surgery", "laparoscopy"],
        "equipment": ["ot", "laparoscope", "xray", "ecg", "icu"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Top-rated surgery centre. Ayushman card accepted. Excellent staff.",
    },
    {
        "name": "Hemant Hospital",
        "address": "Roorkee-Fatehpur-Kalsiya Marg, Ganesh Pur, Roorkee",
        "latitude": 29.8621,
        "longitude": 77.8786,
        "phone": "+91 93592 05044",
        "rating": 4.3,
        "total_beds": 30,
        "available_beds": 12,
        "icu_beds": 4,
        "specialists": ["general_surgery", "laparoscopy"],
        "equipment": ["ot", "laparoscope", "xray", "ecg", "icu"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Dr. Hemant Gupta — best general surgeon per many local reviews.",
    },
    {
        "name": "Pal Clinic & Nursing Home",
        "address": "Durga Chowk, Nehru Stadium Bridge Rd, Veer Bhawan Nagar, Roorkee",
        "latitude": 29.8726,
        "longitude": 77.8842,
        "phone": "+91 1332 275 450",
        "rating": 3.2,
        "total_beds": 20,
        "available_beds": 8,
        "icu_beds": 2,
        "specialists": ["general_surgery", "laparoscopy", "general_medicine"],
        "equipment": ["ot", "xray", "ecg"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Dr. Ramnik Manglik — good surgeon, but admin/punctuality issues noted.",
    },

    # ── ORTHOPAEDICS ────────────────────────────────────────────────────────
    {
        "name": "Mother & Bone Joint Center (Jagannath)",
        "address": "Civil Lines, Roorkee",
        "latitude": 29.8672,
        "longitude": 77.8868,
        "phone": None,
        "rating": 4.7,
        "total_beds": 25,
        "available_beds": 9,
        "icu_beds": 2,
        "specialists": ["orthopaedics", "joint_replacement", "spine"],
        "equipment": ["xray", "ot", "c_arm", "physiotherapy"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Dedicated orthopaedic + bone joint centre.",
    },
    {
        "name": "Palna Bhatnagar Hospital",
        "address": "Civil Lines, Roorkee",
        "latitude": 29.8670,
        "longitude": 77.8880,
        "phone": None,
        "rating": 4.7,
        "total_beds": 30,
        "available_beds": 11,
        "icu_beds": 4,
        "specialists": ["orthopaedics", "cardiology", "general_medicine"],
        "equipment": ["xray", "ecg", "echo", "ot", "c_arm"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Orthopaedic + cardiology combo.",
    },
    {
        "name": "Sarthak Nursing Home",
        "address": "Civil Lines, Roorkee",
        "latitude": 29.8672,
        "longitude": 77.8870,
        "phone": None,
        "rating": 3.9,
        "total_beds": 15,
        "available_beds": 6,
        "icu_beds": 1,
        "specialists": ["orthopaedics", "physiotherapy"],
        "equipment": ["xray", "ot", "physiotherapy"],
        "is_24_7": False,
        "accepts_ayushman": False,
        "notes": "Dr. S.K. Gupta — orthopaedic.",
    },

    # ── EYE HOSPITALS ───────────────────────────────────────────────────────
    {
        "name": "Dhawan Eye Hospitals",
        "address": "Lane 7, near Central Bank, Ramnagar, Roorkee",
        "latitude": 29.8743,
        "longitude": 77.8725,
        "phone": "+91 70171 97023",
        "rating": 5.0,
        "total_beds": 10,
        "available_beds": 4,
        "icu_beds": 0,
        "specialists": ["ophthalmology", "cataract_surgery", "retina"],
        "equipment": ["slit_lamp", "phaco_machine", "oct", "fundus_camera"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Dr. Aeshvarya Dhawan — ~30,000 surgeries. Best eye hospital in Roorkee.",
    },
    {
        "name": "Eye-Q Super Speciality Eye Hospital",
        "address": "Chowmandi, Chand Puri Nagar, Roorkee",
        "latitude": 29.8686,
        "longitude": 77.8801,
        "phone": "+91 80 4485 2763",
        "rating": 4.9,
        "total_beds": 15,
        "available_beds": 6,
        "icu_beds": 0,
        "specialists": ["ophthalmology", "cataract_surgery", "lasik", "retina"],
        "equipment": ["slit_lamp", "phaco_machine", "oct", "lasik_machine", "fundus_camera"],
        "is_24_7": False,
        "accepts_ayushman": True,
        "notes": "National chain. 2190 reviews. 9:30AM–7:30PM.",
    },
    {
        "name": "Vedanta Jyoti Eye Hospital",
        "address": "Chowmandi, Chand Puri Nagar, Roorkee",
        "latitude": 29.8686,
        "longitude": 77.8802,
        "phone": "+91 86506 74273",
        "rating": 4.3,
        "total_beds": 8,
        "available_beds": 3,
        "icu_beds": 0,
        "specialists": ["ophthalmology", "cataract_surgery"],
        "equipment": ["slit_lamp", "phaco_machine", "xray"],
        "is_24_7": False,
        "accepts_ayushman": False,
        "notes": "Dr. Malhotra — good eye specialist.",
    },

    # ── TRAUMA / EMERGENCY ──────────────────────────────────────────────────
    {
        "name": "Saksham Hospital & Trauma Centre",
        "address": "Roorkee",
        "latitude": 29.8700,
        "longitude": 77.8820,
        "phone": None,
        "rating": 3.9,
        "total_beds": 50,
        "available_beds": 18,
        "icu_beds": 10,
        "specialists": ["trauma", "emergency", "general_surgery", "orthopaedics"],
        "equipment": ["xray", "ct_scan", "ot", "icu", "ventilator", "ecg"],
        "is_24_7": True,
        "accepts_ayushman": True,
        "notes": "Dedicated trauma centre. Good for RTA and emergency cases.",
    },

    # ── GOVERNMENT / INSTITUTIONAL ──────────────────────────────────────────
    {
        "name": "Civil Hospital Roorkee",
        "address": "Idgah Chowk, Roorkee",
        "latitude": 29.8792,
        "longitude": 77.8769,
        "phone": None,
        "rating": 3.5,
        "total_beds": 100,
        "available_beds": 40,
        "icu_beds": 8,
        "specialists": [
            "general_medicine",
            "surgery",
            "gynaecology",
            "paediatrics",
            "orthopaedics",
        ],
        "equipment": ["xray", "ultrasound", "ecg", "icu", "ventilator"],
        "is_24_7": False,
        "accepts_ayushman": True,
        "notes": "Government hospital. OPD 8AM–2PM. Free treatment. Ayushman accepted.",
    },
    {
        "name": "Military Hospital Roorkee",
        "address": "Roorkee Cantonment, Roorkee",
        "latitude": 29.8650,
        "longitude": 77.8860,
        "phone": None,
        "rating": 4.2,
        "total_beds": 60,
        "available_beds": 20,
        "icu_beds": 6,
        "specialists": ["general_medicine", "surgery", "ophthalmology"],
        "equipment": ["xray", "ultrasound", "ecg", "icu"],
        "is_24_7": False,
        "accepts_ayushman": False,
        "notes": "Military personnel and families only. General + Eye OPD.",
    },
    {
        "name": "IIT Roorkee Hospital",
        "address": "IIT Campus, Roorkee",
        "latitude": 29.8649,
        "longitude": 77.8614,
        "phone": None,
        "rating": 3.6,
        "total_beds": 30,
        "available_beds": 12,
        "icu_beds": 2,
        "specialists": ["general_medicine"],
        "equipment": ["xray", "ecg", "ultrasound"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "IIT campus hospital. Primarily for students and staff.",
    },

    # ── NURSING HOMES (MIXED) ───────────────────────────────────────────────
    {
        "name": "Bhatnagar Nursing Home",
        "address": "Purvawali, Railway Station Rd, Ganesh Pur, Roorkee",
        "latitude": 29.8581,
        "longitude": 77.8781,
        "phone": "+91 78950 37108",
        "rating": 3.7,
        "total_beds": 20,
        "available_beds": 8,
        "icu_beds": 3,
        "specialists": ["cardiology", "gynaecology", "general_medicine"],
        "equipment": ["ecg", "echo", "ultrasound", "xray"],
        "is_24_7": True,
        "accepts_ayushman": False,
        "notes": "Dr. J.M. Bhatnagar — cardiologist + diabetologist.",
    },
    {
        "name": "Jai Shakuntala Nursing Home",
        "address": "Dehradun Rd, Nehru Nagar, Roorkee",
        "latitude": 29.8687,
        "longitude": 77.8757,
        "phone": "+91 80577 40902",
        "rating": 4.1,
        "total_beds": 15,
        "available_beds": 5,
        "icu_beds": 2,
        "specialists": ["pulmonology", "general_medicine", "tb_chest"],
        "equipment": ["xray", "ecg", "spirometry", "icu"],
        "is_24_7": False,
        "accepts_ayushman": False,
        "notes": "Dr. Parashar — pulmonologist / chest specialist.",
    },
    {
        "name": "Matrachhaya Hospital",
        "address": "Shakumbari Enclave, Delhi Rd, Mohammed Pur, Roorkee",
        "latitude": 29.8333,
        "longitude": 77.8809,
        "phone": "+91 92194 28928",
        "rating": 3.9,
        "total_beds": 25,
        "available_beds": 10,
        "icu_beds": 3,
        "specialists": ["general_medicine", "gynaecology"],
        "equipment": ["xray", "ultrasound", "ecg"],
        "is_24_7": False,
        "accepts_ayushman": True,
        "notes": "Dr. Ajay Panwar — good physician. 10AM–3PM only.",
    },
]

# Map incoming specialties to keys defined in CONDITION_SPECIALIST_MAP
SPECIALISTS_MAP = {
    "neurology": "neurologist",
    "neuro": "neurologist",
    "cardiology": "cardiologist",
    "cardiac": "cardiologist",
    "orthopaedics": "orthopedic",
    "orthopaedic": "orthopedic",
    "ortho": "orthopedic",
    "gynaecology": "gynecologist",
    "gynecologist": "gynecologist",
    "obstetrics": "gynecologist",
    "general_surgery": "general_surgeon",
    "surgery": "general_surgeon",
    "pulmonology": "pulmonologist",
    "paediatrics": "pediatrician",
    "pediatrician": "pediatrician",
    "endocrinology": "endocrinologist",
    "psychiatry": "psychiatrist",
    "ent": "ent_specialist",
    "ophthalmology": "ophthalmologist",
    "gastroenterology": "gastroenterologist",
    "trauma": "general_surgeon",
    "emergency": "emergency_physician"
}

def map_specialists(specs_list):
    res = {}
    for spec in specs_list:
        mapped = SPECIALISTS_MAP.get(spec.lower(), spec.lower())
        res[mapped] = 1
    return res

# ---------------------------------------------------------------------------
# Seeding function
# ---------------------------------------------------------------------------

def seed_hospitals():
    """
    Insert all hospitals into the database.
    """
    db = SessionLocal()
    try:
        inserted = 0
        skipped = 0

        for data in HOSPITALS:
            # Check for duplicates by name
            existing = db.query(Hospital).filter(Hospital.name == data["name"]).first()
            if existing:
                # Update existing availability and specialists
                avail = db.query(Availability).filter(Availability.hospital_id == existing.id).first()
                if avail:
                    avail.beds = data["available_beds"]
                    avail.icu = data["icu_beds"]
                    avail.equipment = data["equipment"]
                    avail.specialists = map_specialists(data["specialists"])
                    avail.updated_at = datetime.now(timezone.utc)
                
                existing.has_icu = data["icu_beds"] > 0
                existing.specialists = map_specialists(data["specialists"])
                db.flush()
                skipped += 1
                continue

            # Build mapped specialists
            specs_dict = map_specialists(data["specialists"])

            # Deduce district from address or defaults
            address_lower = data["address"].lower()
            if "haridwar" in address_lower:
                district = "Haridwar"
            elif "rishikesh" in address_lower:
                district = "Rishikesh"
            else:
                district = "Roorkee"

            hospital = Hospital(
                name=data["name"],
                address=data["address"],
                lat=data["latitude"],
                lng=data["longitude"],
                hospital_type="both",
                has_icu=data["icu_beds"] > 0,
                specialists=specs_dict,
                district=district
            )
            db.add(hospital)
            db.flush()

            availability = Availability(
                hospital_id=hospital.id,
                beds=data["available_beds"],
                icu=data["icu_beds"],
                doctors=max(1, len(data["specialists"])),
                equipment=data["equipment"],
                accepting=True,
                specialists=specs_dict,
                updated_at=datetime.now(timezone.utc)
            )
            db.add(availability)
            inserted += 1

        db.commit()
        print(f"[OK] Seeded {inserted} hospitals | [SKIP/UPDATE] Updated/Skipped {skipped} existing facilities")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seed failed: {e}")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Quick summary export — useful for ML scorer / demo
# ---------------------------------------------------------------------------

def get_hospital_names_by_specialty(specialty: str) -> list[str]:
    """Return hospital names that have a given specialist type."""
    return [
        h["name"]
        for h in HOSPITALS
        if specialty.lower() in [s.lower() for s in h.get("specialists", [])]
    ]


def get_24_7_hospitals() -> list[str]:
    """Return names of all 24/7 hospitals."""
    return [h["name"] for h in HOSPITALS if h.get("is_24_7")]


def get_ayushman_hospitals() -> list[str]:
    """Return names of hospitals accepting Ayushman card."""
    return [h["name"] for h in HOSPITALS if h.get("accepts_ayushman")]


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n[INFO] MediRoute - Roorkee Hospital Seed")
    print(f"   Total facilities: {len(HOSPITALS)}")
    print(f"   24/7 hospitals:   {len(get_24_7_hospitals())}")
    print(f"   Ayushman enabled: {len(get_ayushman_hospitals())}")
    print()

    # Specialty summary
    all_specs = set()
    for h in HOSPITALS:
        all_specs.update(h.get("specialists", []))
    print("[INFO] Specialties covered:")
    for spec in sorted(all_specs):
        hospitals = get_hospital_names_by_specialty(spec)
        print(f"   {spec:<25} -> {len(hospitals)} hospital(s)")

    print("\n[INFO] Seeding database...")
    seed_hospitals()
