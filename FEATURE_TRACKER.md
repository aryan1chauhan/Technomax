# 📊 MediRoute Feature Tracker

This document tracks the implementation status of all major features in the MediRoute application, helping developers identify outstanding tasks and understand the completed scope.

---

## 🚀 Status Table

| Category | Feature | Status | Notes |
|---|---|---|---|
| **Core Platform** | JWT Auth & RBAC | **Done** | Full registration, login, and Role-Based Access Control (Admin, Paramedic, Hospital) implemented. |
| **Dispatch Engine** | ML Hybrid Scorer | **Done** | Hybrid scoring engine utilizing pre-trained `hospital_model.pkl` with a multi-factor weighted rule-based fallback. |
| **Dispatch Engine** | Stability & Triage Engine | **Done** | Evaluates patient vitals and recommends stabilization-first (nearest hospital) vs. direct transport (specialized center). |
| **Dispatch Engine** | Atomic Bed Reservation | **Done** | Atomic locks decrement beds safely upon ambulance dispatch, avoiding race conditions. |
| **Dispatch Engine** | Atomic Bed Restoration | **Done** | Instantly restores beds if a case is declined by a hospital or cancelled by a paramedic. |
| **Real-time** | Live GPS tracking | **Done** | Periodic WebSockets coordinate pings and live ETA updates. |
| **Real-time** | Paramedic-Hospital Chat | **Done** | Instant messaging via unified WebSockets. |
| **Real-time** | WebRTC Voice Calls | **In Progress** | WebSocket signaling protocol is built on the backend, but WebRTC client integration requires further verification. |
| **AI Features** | Voice Dictation Parsing | **Done** | Parses vitals (`spo2`, `pulse`, `bp`) from paramedic speech. Uses Gemini with an offline regex fallback. |
| **Dashboards** | Paramedic Interface | **Done** | Mobile-first dashboard for dispatching, tracking, and messaging. |
| **Dashboards** | Hospital Console | **Done** | Kanban-style incoming ambulance list, live ETAs, and chat. |
| **Dashboards** | Admin Panel | **Done** | System-wide statistics, active case queues, and district loads. |
| **Integrations** | OpenRouteService (ORS) | **Done** | Calculates actual road geometries and ETA. Falls back to Haversine straight-line math if ORS is down. |
| **Integrations** | Firebase Push Alerts | **In Progress** | Backend notification dispatch is complete, but frontend requires actual Firebase configurations in production. |
| **Integrations** | Webhooks Delivery | **Done** | Background queue processes custom webhook events on case state changes. |

---

## 🛠️ Tech Debt & Test Suite Notes

### ⚠️ Critical Test Discrepancies
- **`test_dispatch.py` `/health` Check:** The test case `test_health_check` expects a `"database"` key from the `/health` endpoint, but this database verification check was moved to `/ready` in production.
- **`test_ml_scorer.py` Synchronous Calls:** The hybrid scoring helper `rank_hospitals` was refactored in production to be an asynchronous function (`async def`). However, the test cases in `test_ml_scorer.py` still invoke it synchronously (`scorer.rank_hospitals(...)`), resulting in `TypeError: 'coroutine' object is not subscriptable` failures in the test runner. 
