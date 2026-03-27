# MediRoute — Setup

## Prerequisites
- Docker Desktop installed

## Run
```bash
git clone 
cd "team tech"
docker compose up --build
```

Wait ~60 seconds for first build.

## Seed database (first time only)
```bash
# In a new terminal:
docker exec -i mediroute_db psql -U postgres -d mediroute < backend/seed_data.sql
```

## Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

## Demo logins
| Role | Email | Password |
|------|-------|----------|
| Ambulance | amb1@test.com | test123 |
| Hospital | bhagwati@test.com | test123 |
| Admin | admin@test.com | test123 |
