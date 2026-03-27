# MediRoute — Technical Audit (Part 2: Frontend)

---

## 22. [frontend/src/main.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/main.jsx)

- **Purpose:** React entry point — renders `<App />` into DOM
- **Dependencies:** `react`, `react-dom`, `./index.css`, [./App.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/App.jsx)
- **Key Logic:** Standard Vite+React entry — `createRoot` with `StrictMode`
- **Known Issues:** None

---

## 23. [frontend/src/App.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/App.jsx)

- **Purpose:** React Router configuration — defines all application routes
- **Dependencies:** `react-router-dom`, all page components, [ProtectedRoute](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/components/ProtectedRoute.jsx#3-12)
- **Routes:**

| Path | Component | Auth | Role |
|------|-----------|------|------|
| `/` | → Redirect to `/login` | No | — |
| `/login` | [Login](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/Login.jsx#21-171) | No | — |
| `/dispatch` | [Dispatch](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/Dispatch.jsx#15-174) | Yes | ambulance |
| `/result` | [Result](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/Result.jsx#4-151) | Yes | ambulance |
| `/map` | `MapPage` | Yes | ambulance |
| `/hospital/track/:case_id` | [HospitalTrack](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/HospitalTrack.jsx#34-267) | Yes | hospital |
| `/hospital/dashboard` | [HospitalDashboard](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/HospitalDashboard.jsx#6-227) | Yes | hospital |
| `/admin/dashboard` | [AdminDashboard](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/AdminDashboard.jsx#45-322) | Yes | any |

- **Known Issues:**
  > [!WARNING]
  > 1. [ProtectedRoute](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/components/ProtectedRoute.jsx#3-12) only checks token **existence**, not validity/expiry
  > 2. **No role-based route guards** — any authenticated user can access any route
  > 3. Imports from `./pages/hospital/HospitalTrack` — implies subdirectory, but files listed at [./pages/HospitalTrack.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/HospitalTrack.jsx)

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| APP-1: Unauthenticated redirect | No token | Navigate to `/dispatch` | Redirected to `/login` | Login shown |
| APP-2: Root redirect | Any state | Navigate to `/` | Redirected to `/login` | Login shown |
| APP-3: Authenticated access | Valid token | Navigate to `/dispatch` | Dispatch page renders | Page loads |

---

## 24. [frontend/src/components/ProtectedRoute.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/components/ProtectedRoute.jsx)

- **Purpose:** Route guard — redirects unauthenticated users to login
- **Key Logic:** Checks `localStorage.getItem('token')` — if absent, redirect to `/login`; else render `<Outlet />`
- **Known Issues:** No token **validation** — expired/malformed tokens pass through

---

## 25. [frontend/src/api/axios.js](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/api/axios.js)

- **Purpose:** Axios instance with auto-attached Bearer token
- **Key Logic:** Interceptor reads token from `localStorage` and sets `Authorization` header
- **Known Issues:** `baseURL: ''` — relies on Vite proxy or Nginx proxy for API routing; no error interceptor for 401 (auto-logout)

---

## 26. [frontend/src/pages/Login.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/Login.jsx) (274 lines)

- **Purpose:** Terminal-style login page with boot sequence animation
- **Dependencies:** `react`, `react-router-dom`, `axios`
- **Key Logic:**
  - **Boot sequence:** 12 ASCII lines typed out at 120ms intervals (typewriter effect)
  - **Login form:** Appears after boot; posts to `/api/auth/login`
  - **Role routing:** `ambulance→/dispatch`, `hospital→/hospital/dashboard`, `admin→/admin/dashboard`
  - **Demo credentials shown:** `amb1@test.com`, `bhagwati@test.com`, password: `test123`
- **Design:** Dark terminal aesthetic — monospace font, green-on-black, scanline overlay, blinking cursor
- **Known Issues:**
  > [!WARNING]
  > 1. `role` is extracted from **response data** (`res.data.role`) but the backend login endpoint **does not return `role`** — it only returns `{access_token, token_type}`. This would cause `role` to be `undefined` → wrong redirect.
  > 2. Inline styles (no CSS classes) — hard to maintain

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| LOGIN-1: Successful login | User exists | Enter creds, submit | Token stored, redirect by role | Navigates correctly |
| LOGIN-2: Invalid creds | No such user | Enter bad creds, submit | "ACCESS DENIED" error shown | Error visible |
| LOGIN-3: Boot animation | Page load | Wait 2 seconds | All boot lines appear, form shows | Typewriter completes |

---

## 27. [frontend/src/pages/Dispatch.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/Dispatch.jsx) (204 lines)

- **Purpose:** Ambulance dispatch console — select condition, equipment, auto-detect GPS, dispatch
- **Key Logic:**
  - **GPS auto-detection** via `navigator.geolocation` with Dehradun fallback [(30.3165, 78.0322)](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/App.jsx#11-29)
  - **9 conditions** listed (but backend synthetic data has 20 — **major mismatch**)
  - **6 equipment options** — toggleable checkboxes
  - Posts to `/api/dispatch/` with Bearer token
  - On success: navigates to `/result` passing dispatch response via React Router state
- **Known Issues:**
  > [!CAUTION]
  > 1. **Condition list mismatch** — frontend has 9 conditions (`cardiac_arrest`, `stroke`, `trauma`, `respiratory`, `burns`, `fracture`, `poisoning`, `obstetric`, `general`) while backend training data has 20 conditions. Conditions like `head injury`, `internal bleeding`, `spinal injury` are **missing from the frontend**.
  > 2. Uses `_` separator (`cardiac_arrest`) while backend uses spaces (`cardiac arrest`) — **format mismatch**
  > 3. Hardcoded `188` hospitals in loading text

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| DISP-1: GPS lock | Browser has GPS | Load page | GPS status shows "LOCKED" with coordinates | Coords displayed |
| DISP-2: Dispatch without condition | GPS locked | Click dispatch without selecting condition | "ERR: Select patient condition" | Error shown |
| DISP-3: Successful dispatch | Ambulance token, GPS locked | Select cardiac_arrest + defibrillator, dispatch | Navigate to `/result` with response data | Result page shown |

---

## 28. [frontend/src/pages/Result.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/Result.jsx) (168 lines)

- **Purpose:** Terminal-style dispatch result viewer with typewriter line reveal
- **Key Logic:**
  - Reads result from `location.state` (passed from Dispatch page)
  - Displays: hospital name, address, ML score (with ASCII bar), distance, ETA, beds, ICU, case ID
  - Score color: green >70%, yellow >40%, red <40%
  - Actions: "OPEN NAVIGATION MAP" → passes hospital coords + case ID to Map page; "NEW DISPATCH" → back to dispatch
  - Shows ML reasoning if available
- **Known Issues:** Footer says "RandomForest • 15 features" — hardcoded; may not reflect actual model

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| RES-1: No state | Navigate directly to `/result` | Page loads | Redirects to `/dispatch` | Auto-redirect |
| RES-2: High score display | Score = 0.85 | View result | Green bar, 85.0% shown | Color correct |
| RES-3: Map navigation | Result displayed | Click "OPEN NAVIGATION MAP" | Navigate to `/map` with correct state | Map opens |

---

## 29. [frontend/src/pages/Map.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/Map.jsx) (279 lines)

- **Purpose:** Real-time ambulance tracking map with route animation and WebSocket GPS relay
- **Dependencies:** `mapbox-gl`, OpenRouteService API, WebSocket
- **Key Logic:**
  - **Mapbox GL JS** with dark style, 3D pitch (45°)
  - **Route fetching** via OpenRouteService Directions API
  - **Ambulance animation** along route coordinates at ~1s/point intervals
  - **WebSocket** broadcasts live GPS to hospital (`/ws/ambulance/{case_id}`)
  - ETA countdown updates as ambulance moves
  - Fake "ACTIVE NETWORK LOGS" — random simulated triage events every 8s
- **Known Issues:**
  > [!WARNING]
  > 1. **Mapbox token** defaults to `"YOUR_MAPBOX_TOKEN"` — must be set in [.env](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/.env)
  > 2. **ORS API key** is in frontend [.env](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/.env) — exposed to clients
  > 3. `startPos` reads `data.ambulance_lng/ambulance_lat` but Result page passes `ambLat/ambLng` — **key name mismatch**
  > 4. Simulated logs are fake — misleading for judges
  > 5. **Hooks called conditionally** — `useRef` hooks called after early return (line 31-37) violates Rules of Hooks

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| MAP-1: Route renders | Valid Mapbox + ORS keys | Navigate with valid state | Route drawn, ambulance animates | Route visible |
| MAP-2: No state | Navigate directly | No state passed | Redirect to `/dispatch` | Redirected |
| MAP-3: WebSocket relay | Map + Hospital tracking | Ambulance moves | Hospital receives GPS updates | Data forwarded |

---

## 30. [frontend/src/pages/HospitalDashboard.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/HospitalDashboard.jsx) (227 lines)

- **Purpose:** Hospital dashboard showing incoming emergency cases assigned to this hospital
- **Dependencies:** `jwt-decode`, `api/axios`, `react-leaflet`
- **Key Logic:**
  - Decodes JWT to get `hospital_id` → fetches all user's cases → filters by `assigned_hospital_id`
  - Auto-refreshes every 10 seconds
  - Stats: cases today, active cases, average score
  - Each case card: condition, equipment needed, score bar, distance, ETA, and "Track Ambulance" button
- **Known Issues:**
  > [!WARNING]
  > 1. Fetches from `/api/cases/` (user's own cases) instead of `/api/cases/hospital` — **wrong endpoint**. A hospital user would see cases they dispatched (if any), not cases assigned to their hospital.
  > 2. Uses `className` with Tailwind classes but Tailwind **may not be configured** (it's in devDependencies but no `tailwind.config.js` check was done)
  > 3. CSS uses `bg-[#0F1B2D]` — Tailwind arbitrary values

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| HDASH-1: Cases shown | Hospital has assigned cases | Login as hospital, view dashboard | Cases displayed with correct data | Cards rendered |
| HDASH-2: Auto-refresh | Dashboard open | Wait 10 seconds | Cases refresh without page reload | Data updates |
| HDASH-3: Track ambulance | Case exists | Click "View Emergency" button | Navigate to `/hospital/track/{id}` | Track page opens |

---

## 31. [frontend/src/pages/HospitalTrack.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/HospitalTrack.jsx) (267 lines)

- **Purpose:** Real-time ambulance tracking for hospital staff using Leaflet + WebSocket
- **Dependencies:** `react-leaflet`, `leaflet`, `api/axios`
- **Key Logic:**
  - Fetches case data, opens WebSocket to `/ws/hospital/{case_id}`
  - Displays Leaflet map with ambulance (red) and hospital (green) markers
  - ETA countdown timer (seconds-based)
  - Action buttons: "Mark as Ready" (alert only), "Call Ambulance" (alert only)
- **Known Issues:**
  > [!CAUTION]
  > 1. **HOSPITAL_POS hardcoded** to `[29.8700, 77.8960]` — same position for ALL hospitals regardless of which hospital the user belongs to
  > 2. Case data fetched from `/api/cases/` — filters all user's cases to find the one by ID, but hospital users may not have access to ambulance users' cases
  > 3. Action buttons only show `alert()` — not functional

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| HTRK-1: Live tracking | Ambulance WS active | Open track page for active case | Ambulance marker moves, ETA updates | Real-time updates |
| HTRK-2: Arrival | Ambulance arrives (eta=0) | Watch track page | "ARRIVED" shown, banner turns green | Status updates |
| HTRK-3: Case not found | Invalid case_id | Navigate to `/hospital/track/99999` | "Case not found" message | Graceful error |

---

## 32. [frontend/src/pages/AdminDashboard.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/pages/AdminDashboard.jsx) (322 lines)

- **Purpose:** System-wide admin overview — terminal-style with ASCII charts
- **Dependencies:** `axios`
- **Key Logic:**
  - Fetches `/api/cases/admin/stats` every 15 seconds
  - Displays: total hospitals, beds, ICU, dispatches, district capacity map (ASCII bars), recent 24h cases table, ML engine status
  - Terminal aesthetic matching Login/Dispatch pages
- **Known Issues:**
  > [!WARNING]
  > 1. **ML Engine Status is hardcoded** — says "RandomForest (class_weight=balanced)", "112,800 samples" regardless of actual model
  > 2. Navigation to `/dispatch` available from admin — may not be appropriate for admin role
  > 3. Uses `localStorage.clear()` on logout — clears ALL localStorage, not just token

| Test | Preconditions | Steps | Expected | Pass/Fail |
|------|--------------|-------|----------|-----------|
| ADM-1: Stats load | Admin logged in, cases exist | View dashboard | All stat cards populated | Data shown |
| ADM-2: District breakdown | Hospitals seeded | View district map | 6 districts with ASCII bars | Bars rendered |
| ADM-3: Auto-refresh | Dashboard open | Wait 15 seconds | Stats refresh automatically | Data updates |

---

*Continued in [Part 3: Infrastructure & System Sections](file:///C:/Users/ARYAN/.gemini/antigravity/brain/16d39e28-c05d-4687-a9b8-77b4ca68de89/audit_part3_infra.md)*
