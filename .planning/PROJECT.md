# MediRoute

## What This Is

A real-time, ML-powered hospital-ambulance dispatch system built for a state-level hackathon in Uttarakhand, India. It enables ambulance dispatchers to input emergency cases (manually or via voice-to-text), evaluates 188 local hospitals in real-time based on distance, beds, ICU capacity, and equipment, and automatically computes the best route for the patient.

## Core Value

Zero-latency, intelligent patient routing. If everything else fails, the system must definitively answer "Which hospital is the absolute best match for this severely injured patient *right now*?" and route them there successfully.

## Requirements

### Validated

- [x] Rule-based Matchmaking Engine
- [x] XGBoost ML Hybrid Model integration for hospital scoring
- [x] Real-time WebSocket ambulance tracking
- [x] Voice-to-Text emergency parser (Anthropic Claude 3 Haiku)
- [x] JWT Authentication + RBAC (Admin, Hospital, Ambulance)
- [x] Atomic Database operations for bed deduction
- [x] CI/CD Testing Pipeline via Code Rabbit and Ralph Loop (Pytest & Vitest)

### Active

- [ ] Further autonomous scaling utilizing GSD project pipelines

### Out of Scope

- Billing or patient identity verification beyond emergency contact. — Hackathon context prioritizes rapid dispatch, not hospital admin overhead.

## Context

- The project is fully mature and practically feature complete for a high-stakes hackathon demo.
- Frontend: React (Vite) + Leaflet (Maps) with a hacker-terminal aesthetic.
- Backend: FastAPI + PostgreSQL + ML Scorer (`hospital_model.pkl`).
- GSD has just been fully configured across the system to manage autonomous workflows.

## Constraints

- **Timeline**: Hackathon deadline restricts large structural rewrites.
- **Tech Stack**: Must remain compatible with Docker Compose, FastAPI, and Vite to preserve current deployment ease.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Implement Ralph Loop CI/CD | Validates all code changes autonomously via Git | ✓ Good |
| Atomic Resource Deductions | Prevent race conditions when competing ambulances snipe the same ICU bed | ✓ Good |

---
*Last updated: 2026-04-11 after GSD Initialization*
