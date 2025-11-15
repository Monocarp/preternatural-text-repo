// src/pages/Callback.tsx
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
// # import jwtDecode from 'jwt-decode'
import { jwtDecode } from 'jwt-decode'

const Callback = () => {
  const navigate = useNavigate()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const error = params.get('error')
    const errorDescription = params.get('error_description')
    
    if (error) {
      console.error('Auth error:', error, errorDescription)
      // Redirect to login with error message
      navigate(`/login?error=${encodeURIComponent(errorDescription || error)}`)
      return
    }
    
    if (token) {
      try {
        localStorage.setItem('token', token)
        const decoded = jwtDecode(token)
        console.log('Authenticated user:', decoded)
        // Redirect to the page they were trying to access, or home
        const returnTo = localStorage.getItem('returnTo') || '/'
        localStorage.removeItem('returnTo')
        navigate(returnTo)
      } catch (err) {
        console.error('Error decoding token:', err)
        navigate('/login?error=Invalid token')
      }
    } else {
      console.warn('No token in callback URL')
      navigate('/login?error=No token received')
    }
  }, [navigate])

  return (
    <div className="flex items-center justify-center h-screen bg-gray-900 text-white">
      <div className="text-center">
        <p className="text-lg">Authenticating...</p>
      </div>
    </div>
  )
}

export default Callback