# MediRoute Technical Audit Report - Part 2 (Frontend)

## 22. FILE PATH — frontend/src/main.jsx
**PURPOSE:** The React application entry point.
**DEPENDENCIES:** `react`, `react-dom`, `App.jsx`, `index.css`.
**KEY LOGIC:** Mounts the `<App />` component to the top-level DOM element using `createRoot()`. Includes React StrictMode wrapper.
**INPUTS & OUTPUTS:** Binds React Virtual DOM to Real DOM `div#root`.
**INTEGRATION POINTS:** Bootstraps the entire UI framework.
**KNOWN ISSUES:** None. Standard Vite setup.
**TEST CASES:**
1. **App Mount:** Preconditions: Valid `index.html`. Steps: Load page in browser. Expected Result: React mounts without console errors.

## 23. FILE PATH — frontend/src/App.jsx
**PURPOSE:** Manages application routing and top-level authentication boundaries.
**DEPENDENCIES:** `react-router-dom`, `Login.jsx`, `Dispatch.jsx`, `Map.jsx`, `Result.jsx`, `HospitalDashboard.jsx`, `HospitalTrack.jsx`, `AdminDashboard.jsx`.
**KEY LOGIC:**
- Defines routes via React Router v7 components (`BrowserRouter`, `Routes`, `Route`).
- Uses `<ProtectedRoute>` component to wrap all views that require authentication (everything except `/login`).
- Provides a default redirect from `/` to `/login`.
**INPUTS & OUTPUTS:** React nodes mapping URL paths to Pages.
**INTEGRATION POINTS:** Bridges browser navigation to internal page state.
**KNOWN ISSUES:**
- All roles hit the same authentication guard (`ProtectedRoute`). It does not internally differentiate roles (e.g. forcing an ambulance user strictly out of the `/admin` route). BOLA vulnerabilities exist client-side if a user directly pastes a Hospital URL.
**TEST CASES:**
1. **Public Route:** Preconditions: Not logged in. Steps: Navigate to `/`. Expected Result: Redirects to `/login`.
2. **Protected Route Rejection:** Preconditions: Not logged in. Steps: Navigate to `/dispatch`. Expected Result: Intercepted and forced back to `/login`.
3. **Valid Route Access:** Preconditions: Logged in (has valid localStorage JWT). Steps: Navigate to `/dispatch`. Expected Result: Renders `Dispatch` component.

## 24. FILE PATH — frontend/src/components/ProtectedRoute.jsx
**PURPOSE:** Simple security guard evaluating token presence.
**DEPENDENCIES:** `react-router-dom`.
**KEY LOGIC:** Parses `localStorage.getItem('token')`. If truthy, returns `<Outlet />` allowing render traversal down to the protected component. If falsy, returns `<Navigate to="/login" replace />`.
**INPUTS & OUTPUTS:** Reads browser API context; returns JSX nodes.
**INTEGRATION POINTS:** Wraps child API routes in `App.jsx`.
**KNOWN ISSUES:**
- Relies solely on the *presence* of a plaintext string named `token` in localStorage. Does not check expiry, signature validation, or cryptographic integrity. A user could type `localStorage.setItem('token', 'fake')` in the console and bypass this guard instantly, although backend API calls would naturally fail 401 later.
**TEST CASES:**
1. **Token Present:** Preconditions: Setup dummy token. Steps: Access Outlet. Expected Result: Renders valid child.
2. **Token Missing:** Preconditions: `localStorage.clear()`. Steps: Access Outlet. Expected Result: React Router `Navigate` redirects.

## 25. FILE PATH — frontend/src/api/axios.js
**PURPOSE:** Configures the global `axios` instance for making authenticated HTTP requests to the backend.
**DEPENDENCIES:** `axios`.
**KEY LOGIC:**
- Initializes empty `baseURL` (relying on vite/nginx proxying).
- Installs an interceptor on `request` that automatically checks for `localStorage.getItem('token')` and appends it to the `Authorization: Bearer <token>` header of every outbound API request.
**INPUTS & OUTPUTS:** HTTP request object mutations.
**INTEGRATION POINTS:** Exported globally as `api` and used by literally every page component.
**KNOWN ISSUES:**
- Does not intercept global 401s (Unauth) to trigger a global logout and flush invalid tokens.
**TEST CASES:**
1. **Append Token:** Preconditions: Token present in storage. Steps: Execute `api.get('/test')`. Expected Result: Outbound HTTP headers contain "Bearer [token]".
2. **Handle Null Token:** Preconditions: No token. Steps: Execute `api.get('/test')`. Expected Result: Authorization header is omitted entirely.

## 26. FILE PATH — frontend/src/pages/Login.jsx
**PURPOSE:** Authentication page enabling users to login and get routed to their role-specific dashboard.
**DEPENDENCIES:** `react`, `react-router-dom`, `jwt-decode`, custom API module.
**KEY LOGIC:**
- Maintains state for email, password, loading status, and error messages.
- `handleLogin`: Submits credentials to `/api/auth/login`. On success, extracts the JWT, stores it in `localStorage`.
- Importantly, it leverages `jwt-decode` to decrypt the payload on the client side, reads the `role`, stores it in `localStorage`, and runs a switch statement to dispatch:
    - `hospital` -> `/hospital/dashboard`
    - `admin` -> `/admin`
    - `ambulance` -> `/dispatch`
- Includes terminal CSS aesthetic animations via injected style tags.
**INPUTS & OUTPUTS:** Handles DOM events. Sends POST data. Navigates history.
**INTEGRATION POINTS:** Primary entry sequence. Communicates with `auth.py`.
**KNOWN ISSUES:**
- Plaintext password input visually mapped via CSS. Recreating complex CSS aesthetics over raw form inputs can sometimes break browser autofill or accessibility.
**TEST CASES:**
1. **Missing Data:** Preconditions: None. Steps: Click Login with empty fields. Expected Result: Frontend prevents/warns, or backend throws 422 immediately flagged via `setError`.
2. **Invalid Data:** Preconditions: None. Steps: Submit bad password. Expected Result: Catches Axios 401, displays red error message ("Incorrect email or password").
3. **Role Routing:** Preconditions: None. Steps: Login with hospital account. Expected Result: `jwtDecode` correctly isolates `"hospital"` and pushes router to `/hospital/dashboard`.

## 27. FILE PATH — frontend/src/pages/Dispatch.jsx
**PURPOSE:** The primary Ambulance user interface for inputting emergency details and requesting an optimal hospital.
**DEPENDENCIES:** `react`, `react-router-dom`, custom API module.
**KEY LOGIC:**
- State for selected condition and a complex array of tracked equipment toggles.
- Maps the UI condition dropdown options 1:1 with the 20 conditions defined by the ML generator backend model. Crucial alignment.
- When `handleDispatch` fires, grabs hardcoded/pseudo-GPS coords, POSTs `{condition, equipment_needed, lat, lng}` to `/api/dispatch/`.
- On success, it hijacks the React Router state mechanism to literally push the *entire JSON backend response object* forward into `/result` via `navigate('/result', { state: res.data })`.
**INPUTS & OUTPUTS:** Validates dropdowns and toggles into a payload. Output is purely navigational side-effect.
**INTEGRATION POINTS:** Consumes `/api/dispatch` API. Hands off data to `Result.jsx`.
**KNOWN ISSUES:**
- Passes data tightly coupled via the Router's DOM history state object. If the user refreshes `/result`, the state object vanishes, breaking the page. (Normally solved by passing a `?case_id=X` query param and re-fetching on the next page).
- Hardcodes GPS coordinates to Roorkee instead of using `navigator.geolocation` browser APIs.
**TEST CASES:**
1. **Dropdown Mutability:** Preconditions: None. Steps: Change condition dropdown. Expected Result: Internal state updates accordingly.
2. **Checkbox Toggles:** Preconditions: None. Steps: Click 'ecg' checkbox twice. Expected Result: Adds 'ecg' to `equipment` array on first click, removes it on second click.
3. **Successful POST:** Preconditions: Valid API. Steps: Submit valid form. Expected Result: React router redirects to `/result` holding the heavy payload state.
4. **Failed POST:** Preconditions: API down. Steps: Submit form. Expected Result: Catches Axios error, displays `setError` message, stops spinning loading animation.

## 28. FILE PATH — frontend/src/pages/Result.jsx
**PURPOSE:** Displays the output reasoning, ETA, distance, and scoring breakdown from the ML engine.
**DEPENDENCIES:** `react`, `react-router-dom`.
**KEY LOGIC:**
- Pulls `useLocation().state`. If null (i.e., user navved here directly via URL bar), immediately forces redirect back to `/dispatch`.
- Parses the complex JSON object resulting from the ML prediction. Calculates width bounds for CSS bar representations (like Score percentage `Math.round(x * 100)`).
- Contains logic filtering between "Matched" and "Missing" equipment arrays to build colored indicator pills.
- Two distinct call to actions: "View on Map" (pushes deep URL state to `/map`) and "Cancel" (pops back to `/dispatch`).
**INPUTS & OUTPUTS:** purely static DOM rendering of a prop.
**INTEGRATION POINTS:** Receives baton pass from `Dispatch.jsx`. Hands baton off to `Map.jsx`.
**KNOWN ISSUES:**
- Extremely brittle chained layout dependencies. The entire workflow relies on the user not hitting the browser "Refresh" button.
**TEST CASES:**
1. **Missing State Bounce:** Preconditions: Fresh incognito window. Steps: Navigate `http://localhost/result`. Expected Result: Immediate redirect to `/login` (via ProtectedRoute bounds) then presumably `/dispatch`.
2. **Complete Equipment Match:** Preconditions: State provided where `equipment_missing=[]`. Steps: Render component. Expected Result: Shows distinct green "All equipment available" message block.
3. **Score Bar Rendering:** Preconditions: State `final_score=0.45`. Steps: Render. Expected Result: Internal CSS div width renders linearly via inline styles at exactly `45%`.

## 29. FILE PATH — frontend/src/pages/Map.jsx
**PURPOSE:** Heavy interactive page providing an ambulance driver with live 3D routing, real-time WebSocket vehicle broadcasting, and ETA metrics.
**DEPENDENCIES:** `react`, `react-router-dom`, `@react-google-maps/api`, `lucide-react`.
**KEY LOGIC:**
- Retrieves map configuration from Environment variable `VITE_GOOGLE_MAPS_KEY`.
- Defines complex array maps for 3D orientation (tilt, tracking, pitch bounds).
- Executes `DirectionsService` strictly once using `useEffect` with dependency checks to draw the routing line mapping Ambulance start coord to Hospital end coord. Uses `requestAnimationFrame` for hyper-fluid path tracing interpolations.
- `useWebSocket` hook: opens connection to `ws://host/ws/ambulance/{case_id}`. Emits updated position payloads in a simulated heartbeat.
- Calculates distance covered and auto-triggers "Arrived" fireworks logic when ETA < 0.5.
**INPUTS & OUTPUTS:** Outputs data heavily over WS connection. Inputs simulated clockticks.
**INTEGRATION POINTS:** Sends data over WS to Hospital Track users. Consumes Google Maps API tokens. Consumes route data from `Result.jsx`.
**KNOWN ISSUES:**
- Heavy re-rendering potential. Since GPS state drives Map Center mapping via React state updates, it forces total component diffs several times a second during simulated navigation. Overly complex re-rendering limits low-end tablet FPS.
- VITE ENV maps key leakage is standard practice but means strict HTTP origin locking must be configured inside GCP console.
**TEST CASES:**
1. **WebSocket Connect:** Preconditions: Valid case_id. Steps: Component mounts. Expected Result: Open WebSocket connection firing `onopen`.
2. **Movement Interpolation:** Preconditions: Route defined. Steps: Inspect state over 3s. Expected Result: `ambulancePos` state ticks slowly along the polyline.
3. **Arrived State Trigger:** Preconditions: `eta` ticks down manually. Steps: Force `eta=0`. Expected Result: `arrived` boolean unlocks, DOM updates overlay panels and terminates location broadcasting over WS.

## 30. FILE PATH — frontend/src/pages/HospitalDashboard.jsx
**PURPOSE:** A live-polling dashboard for hospital administrators to view incoming patient dispatches assigned specifically to them.
**DEPENDENCIES:** `react`, `react-router-dom`, custom `axios` API instance.
**KEY LOGIC:**
- Performs an HTTP GET request to `/api/cases/hospital` sequentially every 10,000 milliseconds via `setInterval` in a background `useEffect`.
- Processes raw `cases` lists into filtered lists (e.g. comparing JS `new Date(c.created_at)` against `today.getDate()`) to provide summary "Cases Today" stats.
- Iterates over cases mapping CSS conditionals against ML `final_score` parameters. Provides tracking buttons.
**INPUTS & OUTPUTS:** Reads from REST API list endpoint, renders Dashboard.
**INTEGRATION POINTS:** Backend `/cases/hospital` endpoint.
**KNOWN ISSUES:**
- Short polling interval (10 seconds) isn't terribly heavy, but does not scale beautifully compared to the WebSockets used in routing. It performs full DOM swaps on lists.
- Timezone issues: Hard logic uses local browser `new Date()` matching JS date parameters against ISO-8601 UTC formats emitted by Postgres. Could cause 5-hour discrepancies crossing international lines, but tolerable for a localized India hackathon.
**TEST CASES:**
1. **Empty Loading State:** Preconditions: Loading=True. Steps: Render. Expected Result: Displays animated spinner.
2. **Zero Cases State:** Preconditions: Data returns `[]`. Steps: Render. Expected Result: "No cases assigned yet — standing by".
3. **Polling Update:** Preconditions: API sends 1 case, then 2 cases 10s later. Steps: Wait 15s. Expected Result: Component silently pushes new case row to the top upon tick.

## 31. FILE PATH — frontend/src/pages/HospitalTrack.jsx
**PURPOSE:** The reciprocal view to `Map.jsx`. Shows the hospital staff a map tracking the incoming ambulance broadcasting its location.
**DEPENDENCIES:** `react`, `react-router-dom`, `react-leaflet`, `leaflet`.
**KEY LOGIC:**
- Fixes broken Vite dependency logic for `leaflet` icon URIs programmatically overriding prototype URLs (`delete L.Icon.Default...`).
- Mounts a Leaflet SVG/Tile map via `MapContainer`. Includes `divIcon` definitions generating CSS animations exclusively inside leaflet anchor bounds.
- Connects passive WS listening socket to `ws://host/ws/hospital/{case_id}`.
- Listens for `{lat, lng, eta_minutes}` JSON strings passing through `onmessage` callback. Updates React state tracking bounding arrays.
- Renders `<Marker>` elements interpolating dynamically on screen.
**INPUTS & OUTPUTS:** Subscribes to WS packets. Updates static DOM. Supports PUT requests (`api.put` marking readiness).
**INTEGRATION POINTS:** WebSockets connected to backend tracker mapping to Ambulance client payload sender.
**KNOWN ISSUES:**
- Mixing `leaflet` DOM mutations heavily with React Virtual Tree components (`react-leaflet`) can be notoriously tricky during deep state unmounts (e.g., navigating away quickly might raise Leaflet unhandled memory errors).
- Backend hospital coordinates (`hospLat`, `hospLng`) gracefully chain fallbacks locally indicating potential backend omissions.
**TEST CASES:**
1. **WS Message Receive:** Preconditions: Ambulance route live. Steps: Provide mock payload. Expected Result: Map `Marker` slides to precise new lat/lng payload automatically.
2. **Mark Ready Toggle:** Preconditions: Button disabled=false. Steps: Click 'Mark Ready'. Expected Result: Triggers Axios `PUT /hospitals/{x}/availability`, updates internal boolean `isReady` mutating button style to 'not-allowed'.
3. **Disconnect Reconnect:** Preconditions: WS active. Steps: Force close WS server externally. Expected Result: Timer kicks off, loops gracefully firing connection re-attempts silently without crashing component.

## 32. FILE PATH — frontend/src/pages/AdminDashboard.jsx
**PURPOSE:** High-level metrics view for authorized state administrators containing regional data roll-ups.
**DEPENDENCIES:** `react`, `react-router-dom`, `axios`.
**KEY LOGIC:**
- Queries heavily aggregated data from `/api/cases/admin/stats` utilizing a Bearer token.
- Background polling `setInterval` updates charts every 15,000ms.
- Includes complex formatting components (e.g., `AsciiBar` representing a custom horizontal capacity gauge matching strict green/black aesthetics).
- Renders 4 primary zones: Topline system stats, district capacity maps breaking down localized infrastructure limits, recent historical dispatched events globally, and a static info panel containing model metadata.
**INPUTS & OUTPUTS:** Reads heavily cached/aggregated data from backend. Outputs highly specific dashboard representations.
**INTEGRATION POINTS:** Directly targets backend admin view endpoints.
**KNOWN ISSUES:**
- High dependency on specific endpoint formats like `districts.name` and nested `score`. If the hardcoded ID sets in the backend break, this page breaks fatally (DOM array mapping exceptions on undefined fields).
- Lacks a complex chart library wrapper (like Chart.js/Recharts), building bars exclusively manually via inline styles.
**TEST CASES:**
1. **AsciiBar Generator:** Preconditions: Provide stats max 100, current 45. Steps: Render. Expected Result: Yields a fixed-width visual string approx 45% filled.
2. **Polling Failure Resiliency:** Preconditions: Server shuts down. Steps: Polling loop executes. Expected Result: Catches `error`, updates top-screen text "⚠ ERROR: Failed to fetch stats" without throwing blank screen exception to React ErrorBoundary.
3. **Table Sorting & Presentation:** Preconditions: valid Data array. Steps: Render 5 rows. Expected Result: All table spans line up perfectly inside grid formats matching terminal aesthetic.

## 33. FILE PATH — frontend/index.html & frontend/vite.config.js & frontend/tailwind.config.js
**PURPOSE:** Standard configuration wrappers assembling the client-side SPA logic.
**DEPENDENCIES:** HTML5, Vite tooling, Tailwind JIT compiler logic.
**KEY LOGIC:**
- `index.html` loads the root `id=root` node and entry points the source modules explicitly. Includes standard mobile meta tags.
- `vite.config.js` sets up basic port configs and standard React mounting overrides.
- `tailwind.config.js` configures standard CSS pipeline scanning targeting only `index.html` and `{js,ts,jsx,tsx}` contents.

## 34. FILE PATH — frontend/.env
**PURPOSE:** Contains sensitive global environment keys explicitly designed to be rolled into the compiled client binary.
**KNOWN ISSUES:**
- Since these are prefix `VITE_`, Vite automatically embeds them physically directly into the JS bundle accessible via any Web Inspector window payload chunk search upon deployment. Google maps API keys MUST be secured separately at the GCP level matching CORS/Orgins perfectly to protect accounts from abuse. This relies fundamentally on Google API boundaries, not backend boundaries.
