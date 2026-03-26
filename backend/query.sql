SELECT COUNT(*) FROM hospitals;
SELECT COUNT(*) FROM availabilities;
SELECT COUNT(*) FROM cases;
SELECT COUNT(*) FROM users;
SELECT id, name, beds, icu FROM hospitals JOIN availabilities ON hospital_id=hospitals.id ORDER BY beds DESC LIMIT 5;
