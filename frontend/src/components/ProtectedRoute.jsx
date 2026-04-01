import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { jwtDecode } from 'jwt-decode'

export default function ProtectedRoute({ allowedRoles }) {
  const token = localStorage.getItem('token')
  const location = useLocation()

  if (!token) {
    return <Navigate to="/login" replace />
  }

  try {
    const decoded = jwtDecode(token)

    // Check token expiry
    if (decoded.exp && decoded.exp * 1000 < Date.now()) {
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      return <Navigate to="/login" replace />
    }

    // Check role-based access if allowedRoles specified
    if (allowedRoles && !allowedRoles.includes(decoded.role)) {
      // Redirect to the appropriate dashboard for their role
      const roleRoutes = {
        ambulance: '/dispatch',
        hospital: '/hospital/dashboard',
        admin: '/admin/dashboard',
      }
      const dest = roleRoutes[decoded.role] || '/login'
      if (dest !== location.pathname) {
        return <Navigate to={dest} replace />
      }
    }
  } catch {
    // Invalid token — clear and redirect
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
