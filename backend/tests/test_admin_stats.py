"""
id: ADMIN-STATS-DISTRICT-001
tags: [@regression, @api]
goal: Ensure hospitals with IDs outside legacy hardcoded ranges are correctly grouped by district in admin stats.
setup: Create a hospital with ID 9999 and district 'TestDistrict' and an availability record.
input: GET /api/cases/admin/stats
expected: TestDistrict is present in the response with correct bed counts.
failure_signal: TestDistrict is missing, indicating fallback to hardcoded ID ranges.
"""
import pytest
from app.db.models import Hospital, Availability

class TestAdminStatsEndpoint:
    def test_admin_stats_groups_by_district(self, client, admin_headers, db_session):
        # 1. Setup - Create hospital outside of legacy hardcoded ID ranges
        test_district = "TestDistrict_9999"
        hospital = Hospital(
            id=9999,
            name="Test Hospital 9999",
            address="123 Test St",
            lat=29.0,
            lng=77.0,
            district=test_district
        )
        db_session.add(hospital)
        db_session.flush()
        
        availability = Availability(
            hospital_id=hospital.id,
            beds=10,
            icu=5,
            accepting=True
        )
        db_session.add(availability)
        db_session.commit()
        
        # 2. Execute
        res = client.get("/api/cases/admin/stats", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        
        # 3. Assert
        districts = data.get("districts", [])
        test_district_data = next((d for d in districts if d["name"] == test_district), None)
        
        assert test_district_data is not None, f"District {test_district} missing from admin stats."
        assert test_district_data["hospitals"] == 1
        assert test_district_data["beds"] == 10
        assert test_district_data["icu"] == 5
