import { useMemo } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { jwtDecode } from 'jwt-decode'

export default function ProtectedRoute({ allowedRoles }) {
  const token = localStorage.getItem('token')
  const location = useLocation()

  const decoded = useMemo(() => {
    if (!token) {
      return null
    }

    try {
      return jwtDecode(token)
    } catch {
      return null
    }
  }, [token])

  if (!token) {
    return <Navigate to="/login" replace />
  }

  // eslint-disable-next-line react-hooks/purity
  const isExpired = Boolean(decoded?.exp && decoded.exp * 1000 < Date.now())
  if (isExpired) {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
  }

  if (!decoded || isExpired) {
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

  return <Outlet />
}
