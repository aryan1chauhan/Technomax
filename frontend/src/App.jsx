import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dispatch from "./pages/Dispatch";
import Result from "./pages/Result";
import Map from "./pages/Map";
import HospitalDashboard from "./pages/HospitalDashboard";
import HospitalTrack from "./pages/HospitalTrack"; // FIX #6: was ./pages/hospital/HospitalTrack
import AdminDashboard from "./pages/AdminDashboard";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />

        {/* Ambulance routes */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dispatch" element={<Dispatch />} />
          <Route path="/result" element={<Result />} />
          <Route path="/map" element={<Map />} />
        </Route>

        {/* Hospital routes */}
        <Route element={<ProtectedRoute />}>
          <Route path="/hospital/dashboard" element={<HospitalDashboard />} />
          <Route path="/hospital/track/:case_id" element={<HospitalTrack />} />
        </Route>

        {/* Admin routes */}
        <Route element={<ProtectedRoute />}>
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
