import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dispatch from './pages/Dispatch'
import Result from './pages/Result'
import MapPage from './pages/Map'
import HospitalTrack from './pages/HospitalTrack'
import HospitalDashboard from './pages/HospitalDashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dispatch" element={<Dispatch />} />
          <Route path="/result" element={<Result />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/hospital/track/:case_id" element={<HospitalTrack />} />
          <Route path="/hospital/dashboard" element={<HospitalDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
