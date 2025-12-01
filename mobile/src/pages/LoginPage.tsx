// mobile/src/pages/LoginPage.tsx
import { useNavigate } from 'react-router-dom'
import { SignIn, useUser } from '@stackframe/react'
import { useEffect } from 'react'

export default function LoginPage() {
  const user = useUser()
  const navigate = useNavigate()

  // Redirect if already logged in
  useEffect(() => {
    if (user) {
      const returnTo = sessionStorage.getItem('returnTo') || '/'
      sessionStorage.removeItem('returnTo')
      navigate(returnTo)
    }
  }, [user, navigate])

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center p-6">
      <div className="bg-gray-800 p-6 rounded-xl shadow-lg w-full max-w-sm">
        <h1 className="text-xl font-bold text-white mb-4 text-center">
          Sign In
        </h1>
        
        <SignIn />
        
        <p className="mt-4 text-sm text-gray-400 text-center">
          Sign in to assign stories to categories
        </p>

        <button
          onClick={() => navigate(-1)}
          className="mt-6 w-full py-3 text-gray-400 text-sm"
        >
          ← Go Back
        </button>
      </div>
    </div>
  )
}
