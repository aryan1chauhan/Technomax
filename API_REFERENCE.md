# 📑 MediRoute API Reference

All REST endpoints require the header `Content-Type: application/json`.
Protected endpoints require a JWT bearer token in the `Authorization` header: `Authorization: Bearer <your_jwt_token>`.

---

## 🔒 1. Authentication (`/api/auth`)

### `POST /api/auth/register`
Registers a new user in the system.
- **Request Body:**
  ```json
  {
    "email": "ambulance_roorkee@example.com",
    "password": "password123",
    "role": "ambulance",
    "hospital_id": null
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "id": 4,
    "email": "ambulance_roorkee@example.com",
    "role": "ambulance"
  }
  ```

### `POST /api/auth/login`
Authenticates a user and returns a JWT access token.
- **Request Body:**
  ```json
  {
    "email": "ambulance_roorkee@example.com",
    "password": "password123"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "role": "ambulance",
    "email": "ambulance_roorkee@example.com",
    "hospital_id": null
  }
  ```

---

## 🚑 2. Dispatch Pipeline (`/api/dispatch`)

### `POST /api/dispatch/`
Core decision-making pipeline. Finds the optimal hospital matching patient conditions and vitals. Automatically reserves a bed atomically upon assignment.
- **Headers:** `Authorization: Bearer <token>`
- **Request Body:**
  ```json
  {
    "condition": "cardiac_arrest",
    "custom_condition": "Patient collapsed suddenly",
    "ambulance_lat": 29.8601,
    "ambulance_lng": 77.8868,
    "severity": 4,
    "patient_age": 62,
    "patient_gender": "male",
    "notes": "ECG shows ST-elevation, CPR in progress",
    "vitals": {
      "oxygen": 88.0,
      "pulse": 145.0,
      "bp": "85/50"
    },
    "ambulance_equipment": ["oxygen", "defibrillator"]
  }
  ```
- **Response (200 OK - Successful Dispatch):**
  ```json
  {
    "case_id": 102,
    "status": "dispatched",
    "hospital_id": 1,
    "hospital_name": "Civil Hospital Roorkee",
    "address": "Civil Lines, Roorkee, Uttarakhand 247667",
    "final_score": 0.892,
    "distance_km": 3.8,
    "eta_minutes": 8,
    "beds": 14,
    "icu": 2,
    "equipment_matched": ["oxygen", "defibrillator"],
    "equipment_missing": [],
    "hospital_lat": 29.8601,
    "hospital_lng": 77.8868,
    "ml_reasoning": [
      "Nearest high-capability cardiac center.",
      "Atomic bed reserved successfully."
    ],
    "decision_type": "direct"
  }
  ```
- **Response (200 OK - No Match Found / Fallback):**
  ```json
  {
    "no_match": true,
    "no_match_reason": "No hospitals passed hard equipment/ICU constraints.",
    "fallback_options": [
      "Civil Hospital Roorkee — ETA 12.4 min",
      "Max Care Hospital Haridwar — ETA 24.1 min"
    ]
  }
  ```

---

## 📋 3. Emergency Cases (`/api/cases`)

### `GET /api/cases/`
Retrieves a list of cases dispatched by the authenticated paramedic.
- **Headers:** `Authorization: Bearer <token>` (Ambulance role)
- **Response (200 OK):**
  ```json
  [
    {
      "id": 102,
      "condition": "cardiac_arrest",
      "hospital_name": "Civil Hospital Roorkee",
      "final_score": 0.892,
      "distance_km": 3.8,
      "eta_minutes": 8,
      "status": "dispatched",
      "created_at": "2026-05-27T04:30:00Z"
    }
  ]
  ```

### `GET /api/cases/hospital`
Retrieves active cases assigned to the authenticated hospital from the last 24 hours.
- **Headers:** `Authorization: Bearer <token>` (Hospital role)
- **Response (200 OK):**
  ```json
  [
    {
      "id": 102,
      "condition": "cardiac_arrest",
      "ambulance_lat": 29.8601,
      "ambulance_lng": 77.8868,
      "status": "dispatched",
      "notes": "CPR in progress",
      "created_at": "2026-05-27T04:30:00Z"
    }
  ]
  ```

### `GET /api/cases/admin/stats`
Retrieves system-wide performance indicators, active case queues, and district loads.
- **Headers:** `Authorization: Bearer <token>` (Admin role)
- **Response (200 OK):**
  ```json
  {
    "total_hospitals": 4,
    "accepting_hospitals": 4,
    "total_beds": 40000,
    "total_icu": 40000,
    "total_cases": 86,
    "cases_last_24h": 12,
    "recent_cases": [...],
    "districts": [
      {
        "name": "Roorkee",
        "hospitals": 2,
        "beds": 20000,
        "icu": 20000,
        "accepting": 2
      }
    ]
  }
  ```

### `PUT /api/cases/{case_id}/status`
Updates case progression status. Enforces strict transitions (e.g., `dispatched` → `accepted` → `arrived` → `completed`).
- **Headers:** `Authorization: Bearer <token>`
- **Request Body:**
  ```json
  {
    "status": "arrived",
    "note": "Ambulance arrived at Emergency Room bay"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "id": 102,
    "status": "arrived",
    "updated_at": "2026-05-27T04:38:00Z"
  }
  ```

### `POST /api/cases/{case_id}/accept`
Quick endpoint for hospitals to accept an inbound patient.
- **Headers:** `Authorization: Bearer <token>` (Hospital role)
- **Response (200 OK):**
  ```json
  {
    "id": 102,
    "status": "accepted"
  }
  ```

### `POST /api/cases/{case_id}/decline`
Quick endpoint for hospitals to decline a patient. **Enforces atomic bed restoration** (increases available beds by 1 immediately).
- **Headers:** `Authorization: Bearer <token>` (Hospital role)
- **Request Body:**
  ```json
  {
    "reason": "Sudden local trauma surge, ICU saturated."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "id": 102,
    "status": "declined"
  }
  ```

---

## 💬 4. Case Chat & History (`/api/cases/{case_id}`)

### `GET /api/cases/{case_id}/timeline`
Returns audit events and state transitions for a case.
- **Headers:** `Authorization: Bearer <token>`
- **Response (200 OK):**
  ```json
  [
    {
      "id": 15,
      "case_id": 102,
      "status": "dispatched",
      "actor_role": "system",
      "note": "Case dispatched by system",
      "timestamp": "2026-05-27T04:30:00Z"
    },
    {
      "id": 16,
      "case_id": 102,
      "status": "accepted",
      "actor_role": "hospital",
      "note": "Case accepted by hospital",
      "timestamp": "2026-05-27T04:32:00Z"
    }
  ]
  ```

### `GET /api/cases/{case_id}/messages`
Retrieves chat messages between paramedic and hospital.
- **Headers:** `Authorization: Bearer <token>`
- **Query Params:** `page` (default 1), `limit` (default 50)
- **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "id": 4,
        "case_id": 102,
        "sender_id": 2,
        "sender_role": "ambulance",
        "sender_email": "ambulance@example.com",
        "body": "Patient vitals stable. ETA 5 minutes.",
        "sent_at": "2026-05-27T04:33:00Z"
      }
    ],
    "page": 1,
    "limit": 50,
    "total": 1
  }
  ```

### `POST /api/cases/{case_id}/messages`
Sends a new chat message and broadcasts it live over WebSocket.
- **Headers:** `Authorization: Bearer <token>`
- **Request Body:**
  ```json
  {
    "body": "Running on high flow oxygen now."
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "id": 5,
    "case_id": 102,
    "sender_role": "ambulance",
    "body": "Running on high flow oxygen now.",
    "sent_at": "2026-05-27T04:34:00Z"
  }
  ```

---

## 🤖 5. Artificial Intelligence (`/api/ai` & `/api/voice`)

### `POST /api/ai/analyze`
Submits raw medical descriptions to Gemini to parse details.
- **Request Body:**
  ```json
  {
    "input": "Elderly patient showing signs of stroke, slurred speech, right side weakness"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "result": {
      "condition": "stroke",
      "severity": "critical",
      "equipment": ["ct_scan", "neurology"],
      "reasoning": "Classic symptoms of acute stroke require urgent neuro-imaging."
    }
  }
  ```

### `POST /api/ai/equipment-recommend`
Called by the frontend to recommend equipment during voice dictation. Falls back gracefully to regexes when the Gemini key is absent.
- **Request Body:**
  ```json
  {
    "voice_text": "Heart rate is 140, chest tightness, need defibrillator ready."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "condition_label": "Cardiac Arrest",
    "severity": 4,
    "severity_label": "Critical",
    "critical_equipment": ["defibrillator"],
    "important_equipment": ["ecg_monitor", "ventilator"],
    "optional_equipment": [],
    "recommended_equipment": ["defibrillator", "ecg_monitor", "ventilator"],
    "notes": "Rule-based assessment (AI offline). Voice: Heart rate is 140...",
    "matched_condition_id": "cardiac_arrest"
  }
  ```

### `POST /api/voice/parse`
Parses voice speech transcripts specifically for vitals. Uses Gemini with an offline keyword/regex fallback.
- **Request Body:**
  ```json
  {
    "transcript": "spo2 is 92 percent, pulse is 95, bp is 130 over 80"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "severity": null,
    "spo2": 92,
    "pulse": 95,
    "bp_systolic": 130,
    "bp_diastolic": 80,
    "confidence": {
      "severity": 0.0,
      "spo2": 0.9,
      "pulse": 0.9,
      "bp_systolic": 0.9,
      "bp_diastolic": 0.9
    },
    "source": "rule_based"
  }
  ```

---

## 🔌 6. WebSockets (`/ws/track/{case_id}`)

A single, unified bidirectional WebSocket channel that coordinates high-frequency tracking, real-time chats, status transitions, and WebRTC voice signaling.

- **URL:** `ws://localhost:8000/ws/track/{case_id}?token=<jwt_token>`

### 📨 Client → Server Events
1. **GPS Positioning Ping:**
   ```json
   {
     "type": "ping",
     "lat": 29.8642,
     "lng": 77.8912,
     "speed_kmh": 42.5
   }
   ```
2. **Status Progression Update:**
   ```json
   {
     "type": "status",
     "status": "arrived"
   }
   ```
3. **WebRTC Signaling Voice Channel (offers, answers, ice candidates):**
   ```json
   {
     "type": "webrtc_offer",
     "payload": { ... }
   }
   ```

### 📩 Server → Client Broadcasts
1. **Route Initialization (`route_init`):**
   Broadcasts base Leaflet map routing geometries.
   ```json
   {
     "type": "route_init",
     "coords": [[29.8601, 77.8868], ...],
     "eta_minutes": 8,
     "total_distance_km": 3.8,
     "road_type": "residential",
     "confidence": 0.95
   }
   ```
2. **Ambulance Live Tracking Ping (`position`):**
   Broadcasts periodic ambulance positions with recalculating ETAs.
   ```json
   {
     "type": "position",
     "case_id": 102,
     "lat": 29.8642,
     "lng": 77.8912,
     "eta_minutes": 6,
     "delta_minutes": -2,
     "remaining_km": 2.6,
     "confidence": 0.92,
     "congested": false,
     "observed_speed_kmh": 42.5,
     "predicted_speed_kmh": 40.0
   }
   ```
3. **Real-time Chat Broadcast (`chat`):**
   ```json
   {
     "type": "chat",
     "case_id": 102,
     "message": {
       "id": 6,
       "sender_role": "ambulance",
       "body": "Entering Haridwar highway now.",
       "sent_at": "2026-05-27T04:35:00Z"
     }
   }
   ```
