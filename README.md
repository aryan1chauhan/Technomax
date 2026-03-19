<p align="center">
  <h1 align="center">🚑 MediRoute</h1>
  <p align="center">
    <strong>Intelligent Ambulance Dispatch & Hospital Routing System</strong>
  </p>
  <p align="center">
    <a href="#features">Features</a> •
    <a href="#tech-stack">Tech Stack</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#api-reference">API Reference</a>
  </p>
</p>

---

## 📌 Overview

**MediRoute** is a full-stack hospital-ambulance dispatch system that intelligently routes ambulances to the best-suited hospital based on real-time availability, distance, and equipment needs. It uses a weighted scoring algorithm combining bed availability, proximity (via the Haversine formula), and medical equipment matching to assign hospitals — ensuring faster, smarter emergency response.

---

## ✨ Features

- **Smart Hospital Scoring** — Weighted algorithm (40% availability, 35% distance, 25% equipment) ranks hospitals in real-time.
- **Haversine Distance Calculation** — Accurate geographic distance between ambulance and hospitals.
- **ETA Estimation** — Estimated arrival time based on distance and average speed.
- **JWT Authentication** — Secure role-based access for dispatchers and hospital admins.
- **Real-Time Availability** — Hospitals can update beds, ICU slots, doctors, and equipment status.
- **Interactive Map View** — Google Maps integration to visualize ambulance and hospital locations.
- **Case History** — Full dispatch case logging with assigned hospital, score, and ETA.
- **Modern React Frontend** — Responsive UI built with React 19, Tailwind CSS, and Vite.

---

## 🛠 Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | High-performance REST API framework |
| **SQLAlchemy** | ORM for database operations |
| **PostgreSQL** | Relational database |
| **Pydantic** | Data validation and serialization |
| **JWT (python-jose)** | Authentication & authorization |
| **Passlib (bcrypt)** | Password hashing |
| **Uvicorn** | ASGI server |

### Frontend
| Technology | Purpose |
|---|---|
| **React 19** | UI component library |
| **Vite** | Fast build tool and dev server |
| **Tailwind CSS** | Utility-first CSS framework |
| **React Router v7** | Client-side routing |
| **Axios** | HTTP client for API calls |
| **Google Maps API** | Interactive map visualization |
| **Lucide React** | Icon library |

---

## 🏗 Architecture

```
Technomax/
├── backend/
│   ├── app/
│   │   ├── api/endpoints/      # REST API routes
│   │   │   ├── auth.py         # Login & registration
│   │   │   ├── hospitals.py    # Hospital CRUD & availability
│   │   │   ├── dispatch.py     # Ambulance dispatch logic
│   │   │   └── cases.py        # Case history
│   │   ├── core/
│   │   │   ├── config.py       # Environment settings
│   │   │   └── security.py     # JWT & password utilities
│   │   ├── db/
│   │   │   ├── database.py     # Database connection
│   │   │   └── models.py       # SQLAlchemy models
│   │   ├── engine/
│   │   │   ├── scorer.py       # Hospital scoring algorithm
│   │   │   └── haversine.py    # Distance calculation
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   └── main.py             # FastAPI app entrypoint
│   ├── seed_db.py              # Database seeding script
│   ├── test_api.py             # API test script
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx       # Authentication page
│   │   │   ├── Dispatch.jsx    # Dispatch form & controls
│   │   │   ├── Result.jsx      # Hospital recommendation view
│   │   │   └── Map.jsx         # Google Maps visualization
│   │   ├── api/                # Axios API client
│   │   ├── components/         # Shared UI components
│   │   ├── App.jsx             # Root component & routing
│   │   └── main.jsx            # React entry point
│   ├── package.json
│   └── tailwind.config.js
└── .gitignore
```

---

## 🧠 Scoring Algorithm

Each hospital is ranked using a composite score:

```
Final Score = (Availability × 0.40) + (Distance Score × 0.35) + (Equipment Score × 0.25)
```

| Factor | Weight | Formula |
|---|---|---|
| **Availability** | 40% | `min(beds / 10, 1.0)` |
| **Distance** | 35% | `1 / (1 + distance_km)` |
| **Equipment** | 25% | `matched / needed` |

- Hospitals that are **not accepting** patients or have **0 beds** are automatically excluded.
- **ETA** is estimated as `(distance_km / 40) × 60` minutes.

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- **PostgreSQL** database
- **Google Maps API Key** (for the map view)

### 1. Clone the Repository

```bash
git clone https://github.com/aryan1chauhan/Technomax.git
cd Technomax
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/mediroute
SECRET_KEY=your-secret-key-here
```

```bash
# Seed the database with sample hospitals
python seed_db.py

# Start the backend server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive Swagger documentation.

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

Create a `.env` file in `frontend/`:

```env
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_MAPS_KEY=your-google-maps-api-key
```

```bash
# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## 📡 API Reference

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/auth/register` | Register a new user | ❌ |
| `POST` | `/auth/login` | Login & get JWT token | ❌ |
| `GET` | `/hospitals/` | List all hospitals | ✅ |
| `GET` | `/hospitals/{id}/availability` | Get hospital availability | ✅ |
| `PUT` | `/hospitals/{id}/availability` | Update hospital availability | ✅ |
| `POST` | `/dispatch/` | Find best hospital for a case | ✅ |
| `GET` | `/cases/` | Get dispatch case history | ✅ |

> Full interactive docs available at `/docs` (Swagger UI) when the backend is running.

---

## 📊 Database Schema

```mermaid
erDiagram
    USERS {
        int id PK
        string email UK
        string password_hash
        string role
        int hospital_id FK
        datetime created_at
    }
    HOSPITALS {
        int id PK
        string name
        string address
        float lat
        float lng
    }
    AVAILABILITIES {
        int id PK
        int hospital_id FK
        int beds
        int icu
        int doctors
        array equipment
        boolean accepting
        datetime updated_at
    }
    CASES {
        int id PK
        int user_id FK
        string condition
        array equipment_needed
        float ambulance_lat
        float ambulance_lng
        int assigned_hospital_id FK
        float final_score
        float distance_km
        int eta_minutes
        datetime created_at
    }
    USERS ||--o{ CASES : creates
    HOSPITALS ||--o| AVAILABILITIES : has
    HOSPITALS ||--o{ CASES : assigned_to
    USERS }o--o| HOSPITALS : belongs_to
```

---

## 👥 Team

Built by **Team Technomax**

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
