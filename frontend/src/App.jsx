import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import RouteFallback from "./components/RouteFallback";
import ErrorBoundary from "./components/ErrorBoundary";
import BackendWakeUp from "./components/BackendWakeUp";
import { ToastProvider } from "./components/Toast";

const Login           = lazy(() => import("./pages/Login"));
const Dispatch        = lazy(() => import("./pages/Dispatch"));
const Result          = lazy(() => import("./pages/Result"));
const Map             = lazy(() => import("./pages/Map"));
const HospitalDashboard = lazy(() => import("./pages/HospitalDashboard"));
const HospitalTrack   = lazy(() => import("./pages/HospitalTrack"));
const AdminDashboard  = lazy(() => import("./pages/AdminDashboard"));
const NotFound        = lazy(() => import("./pages/NotFound"));

import { app } from "./firebase";
if (import.meta.env.DEV) console.log("🔥 Firebase initialized:", app);

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <BrowserRouter>
          {/* Non-blocking cold-start banner for Render free tier */}
          <BackendWakeUp />

          <Suspense fallback={<RouteFallback label="Loading app view..." />}>
            <Routes>
              <Route path="/" element={<Navigate to="/login" replace />} />
              <Route path="/login" element={<Login />} />

              <Route element={<ProtectedRoute allowedRoles={["ambulance"]} />}>
                <Route path="/dispatch" element={<Dispatch />} />
                <Route path="/result"   element={<Result />} />
                <Route path="/map"      element={<Map />} />
              </Route>

              <Route element={<ProtectedRoute allowedRoles={["hospital"]} />}>
                <Route path="/hospital/dashboard"        element={<HospitalDashboard />} />
                <Route path="/hospital/track/:case_id"   element={<HospitalTrack />} />
              </Route>

              <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
                <Route path="/admin/dashboard" element={<AdminDashboard />} />
              </Route>

              {/* 404 catch-all */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ToastProvider>
    </ErrorBoundary>
  );
}
