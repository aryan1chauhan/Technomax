# MediRoute - AI Handoff & Project Context Document

> **Instructions for the AI reading this:** 
> I am handing this project over to you. You currently know nothing about it. Read this document carefully to understand the architecture, tech stack, business logic, and current state of the application. Do not make any changes yet, just acknowledge that you understand the context and wait for my first prompt.

---

## 1. Project Overview
**Name:** MediRoute
**Purpose:** A real-time, ML-powered hospital-ambulance dispatch system built for a state-level hackathon in Uttarakhand, India.
**Core Workflow:** An ambulance dispatcher inputs an emergency case (or uses Voice-to-Text AI). The system's Machine Learning engine evaluates 188 local hospitals in real-time based on distance, bed availability, ICU capacity, and equipment match, then automatically routes the ambulance to the best-suited hospital.

## 2. Tech Stack
*   **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, Pydantic, Uvicorn.
*   **Frontend:** React (Vite), React Router v6, Leaflet (Maps), Axios, custom CSS (Tailwind-like utility classes).
*   **Machine Learning:** Scikit-Learn, XGBoost (predictive scoring for hospital selection).
*   **AI Integration:** Anthropic Claude 3 Haiku (for parsing voice transcripts into emergency conditions & equipment lists).
*   **Real-time:** WebSockets (FastAPI + React) for live ambulance GPS tracking.

## 3. Architecture & Key Features

### Backend (`/backend`)
*   **`app/api/endpoints/`**: 
    *   `dispatch.py`: Core routing logic. Calls the ML engine.
    *   `hospitals.py`: CRUD and live availability updates (beds, ICU, equipment).
    *   `auth.py`: JWT-based Role-Based Access Control (Roles: `admin`, `hospital`, `ambulance`).
    *   `tracking.py`: WebSocket endpoints for real-time map location broadcasts.
    *   `ai.py`: Proxies calls to the Anthropic API to parse raw voice transcripts into structured JSON (`custom_condition`, `severity`, `recommended_equipment`).
*   **`app/engine/ml_scorer.py`**: The hybrid matchmaking engine. First tries to use a trained XGBoost model (`hospital_model.pkl`) to rank hospitals. Falls back to a deterministic rule-based formula if the ML model fails.
*   **`app/db/`**: Defines SQLAlchemy models (`User`, `Hospital`, `Availability`, `Case`).

### Frontend (`/frontend/src/`)
*   **Design System:** A premium, dark "hacker-terminal" aesthetic (Navy `#0D1830`, White cards, Blue/Red/Green accents).
*   **`pages/Login.jsx`**: Split-panel login. Client-side JWT decoding to route users based on role.
*   **`pages/Dispatch.jsx`**: The command center. Features a Web Speech API microphone button that captures voice, sends it to the backend AI, and automatically checks required equipment boxes.
*   **`pages/Result.jsx`**: Displays the winning hospital, ML match score (e.g., 94%), ETA, distance, and ML reasoning.
*   **`pages/Map.jsx`**: 3D Leaflet map that tracks the ambulance to the hospital using WebSockets and `requestAnimationFrame` for smooth 60fps movement.
*   **`pages/HospitalDashboard.jsx` & `AdminDashboard.jsx`**: Polling/live dashboards showing incoming cases, district hospital capacities, and system-wide ML statistics.

## 4. Current State & Recent Work
The project is currently in a highly-polished, feature-complete state for a hackathon demo. 

**Recently Completed Tasks:**
1.  **Massive UI Overhaul:** Completely redesigned the frontend from basic components to a high-end Figma-based design.
2.  **Voice-to-AI Dispatch:** Implemented browser-native Web Speech API. The paramedic speaks, the transcript is sent to Claude via the backend, and the UI automatically populates conditions and equipment requirements.
3.  **Database Evolution:** Upgraded the `Case` table to include `custom_condition` and `notes` to support the new AI parameters without breaking legacy strict rules.
4.  **Security & API Fixes:** Routed the Anthropic API call through the FastAPI backend to prevent frontend CORS errors and secure the API key.

## 5. Known Quirks / Development Notes
*   **Authentication:** The backend `/api/auth/login` endpoint only returns an `access_token` and `token_type`. The frontend uses `jwt-decode` to extract the `role` from the token payload to determine routing.
*   **Maps API:** Maps default to Dehradun/Roorkee coordinates if GPS permissions are denied.
*   **Starting the App:** 
    *   Backend: `cd backend && uvicorn app.main:app --reload`
    *   Frontend: `cd frontend && npm run dev`

---
*End of Context Document.*
