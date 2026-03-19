import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/axios'

const CONDITIONS = [
  'cardiac arrest',
  'stroke',
  'trauma',
  'respiratory failure',
  'burns',
]

const EQUIPMENT_OPTIONS = [
  'ecg',
  'ventilator',
  'defibrillator',
  'xray',
  'icu',
  'blood_bank',
]

export default function Dispatch() {
  const [condition, setCondition] = useState('')
  const [equipment, setEquipment] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const toggleEquipment = (item) => {
    setEquipment((prev) =>
      prev.includes(item) ? prev.filter((e) => e !== item) : [...prev, item]
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!condition) {
      setError('Please select a patient condition')
      return
    }
    setError('')
    setLoading(true)

    try {
      const res = await api.post('/api/dispatch/', {
        condition,
        equipment_needed: equipment,
        ambulance_lat: 29.8543,
        ambulance_lng: 77.8880,
      })
      navigate('/result', { 
        state: { 
          ...res.data, 
          case_id: res.data.case_id  
        } 
      })
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Dispatch failed. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <span className="text-lg font-bold text-gray-900">MediRoute</span>
          </div>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-red-600 font-medium transition"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-2xl mx-auto px-4 py-10">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-1">New Dispatch</h2>
          <p className="text-sm text-gray-500 mb-6">
            Select the patient condition and required equipment to find the best hospital.
          </p>

          {/* Error Message */}
          {error && (
            <div className="mb-5 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Condition Dropdown */}
            <div>
              <label htmlFor="condition" className="block text-sm font-medium text-gray-700 mb-1">
                Patient Condition
              </label>
              <select
                id="condition"
                value={condition}
                onChange={(e) => setCondition(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              >
                <option value="">Select condition...</option>
                {CONDITIONS.map((c) => (
                  <option key={c} value={c}>
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Equipment Checkboxes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Equipment Needed
              </label>
              <div className="grid grid-cols-2 gap-3">
                {EQUIPMENT_OPTIONS.map((item) => (
                  <label
                    key={item}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition ${
                      equipment.includes(item)
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={equipment.includes(item)}
                      onChange={() => toggleEquipment(item)}
                      className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-gray-700 uppercase">
                      {item.replace('_', ' ')}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                  </svg>
                  Finding hospital...
                </>
              ) : (
                'Find Best Hospital'
              )}
            </button>
          </form>
        </div>
      </main>
    </div>
  )
}
