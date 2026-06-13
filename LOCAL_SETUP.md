# 🚀 MediRoute — Run on Another Laptop

Copy the entire `team tech` folder to the other laptop via USB / Google Drive / etc.

> 💡 **Save space:** Delete `backend\.venv\` and `frontend\node_modules\` before copying (~800MB). They get rebuilt automatically.

---

## Pick a Method

| Method | What to Install | Difficulty | Time |
|--------|----------------|------------|------|
| **Method 1: Docker** | Docker Desktop only | ⭐ Easiest | ~3 min |
| **Method 2: setup.bat** | Python + Node.js + PostgreSQL | ⭐⭐ Easy | ~5 min |
| **Method 3: Manual** | Python + Node.js + PostgreSQL | ⭐⭐⭐ | ~10 min |

---

## Method 1: Docker (Recommended)

**Install only one thing:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

Then:
1. Copy the folder to the other laptop
2. Open Docker Desktop (wait for it to start)
3. **Double-click `docker-start.bat`**
4. Wait ~3 minutes → browser opens automatically

**App runs at:** http://localhost:3000

---

## Method 2: setup.bat + start.bat

**Install these 3 things:**
- [Python 3.12+](https://www.python.org/downloads/) — ⚠️ Check **"Add to PATH"** during install!
- [Node.js 18+](https://nodejs.org/)
- [PostgreSQL 15+](https://www.postgresql.org/downloads/) — remember the password you set

Then:
1. Copy the folder to the other laptop
2. **Double-click `setup.bat`** → enter PostgreSQL password → wait ~2 min
3. **Double-click `start.bat`** every time you want to run

**App runs at:** http://localhost:5173

---

## Method 3: Manual (Terminal Commands)

**Install:** Python 3.12+, Node.js 18+, PostgreSQL 15+

### Terminal 1 — Backend
```powershell
cd "team tech\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Create database
psql -U postgres -c "CREATE DATABASE mediroute;"

# Set environment (edit YOUR_PASSWORD)
# Create .env file with:
#   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/mediroute
#   SECRET_KEY=mediroute_uttarakhand_2026_xK9mP2vL
#   ALGORITHM=HS256
#   ACCESS_TOKEN_EXPIRE_MINUTES=60
#   GEMINI_API_KEY=AIzaSyABnWRG8dHETiDyOQE9PIlFJQ36PMbJpsA
#   ORS_API_KEY=eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImZmNzEyNTRmOTMyMmEzYTY0OTgxMDI0YzVkNzM1OTNhYmFmNjMwZjgzYTg0ZmVmMTNjYmRkYTBlIiwiaCI6Im11cm11cjY0In0=
#   FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
#   MODEL_SHA256=a46ae388b1fdc321edd355a3ae431d0eb5cd85f109227563d39c6edd8ee776b7

alembic upgrade head
python seed_db.py
python seed_hospitals_roorkee.py
python seed_users.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — Frontend
```powershell
cd "team tech\frontend"
npm install
npm run dev
```

**App runs at:** http://localhost:5173

---

## Login Credentials (All Methods)

| Role | Email | Password |
|------|-------|----------|
| 🔑 Admin | `admin@test.com` | `test123` |
| 🚑 Ambulance | `amb1@test.com` | `test123` |
| 🏥 Hospital | `hospital@test.com` | `test123` |
| 🏥 Hospital | `bhagwati@test.com` | `test123` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Docker: "Docker daemon not running" | Open Docker Desktop app first, wait 30 sec |
| `python` not recognized | Reinstall Python, check **"Add to PATH"** |
| `psql` not recognized | Add `C:\Program Files\PostgreSQL\15\bin` to system PATH |
| Frontend "Network Error" | Make sure backend terminal is still running |
| Port already in use | Close other apps or change port in the command |
