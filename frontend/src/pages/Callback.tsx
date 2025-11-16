// src/pages/Callback.tsx
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStackApp } from '@stackframe/react'

const Callback = () => {
  const navigate = useNavigate()
  const app = useStackApp()

  useEffect(() => {
    // Stack Auth handles OAuth callbacks automatically when using tokenStore: 'cookie'
    // The SignIn component should have already processed the callback and set cookies
    // We just need to wait a moment for the auth state to sync, then redirect
    
    const checkAuth = async () => {
      try {
        // Wait a moment for Stack Auth to process the callback
        await new Promise(resolve => setTimeout(resolve, 500))
        
        // Check if user is authenticated
        const user = await app.getUser()
        if (user) {
          console.log('Authenticated user:', user)
          // Redirect to the page they were trying to access, or home
          const returnTo = sessionStorage.getItem('returnTo') || localStorage.getItem('returnTo') || '/'
          sessionStorage.removeItem('returnTo')
          localStorage.removeItem('returnTo')
          navigate(returnTo)
        } else {
          // If not authenticated after callback, redirect to login
          console.warn('User not authenticated after callback')
          navigate('/login?error=Authentication failed')
        }
      } catch (err) {
        console.error('Error checking auth state:', err)
        navigate('/login?error=Authentication error')
      }
    }
    
    checkAuth()
  }, [navigate, app])

  return (
    <div className="flex items-center justify-center h-screen bg-gray-900 text-white">
      <div className="text-center">
        <p className="text-lg">Authenticating...</p>
      </div>
    </div>
  )
}

export default Callback