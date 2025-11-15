// src/components/Login.tsx
import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SignIn } from '@stackframe/react' // Updated import for correct package

const Login = () => {
  const [error, setError] = useState<string | null>(null)
  const [searchParams] = useSearchParams()
  
  // Check for error in URL params (from callback)
  useEffect(() => {
    const errorParam = searchParams.get('error')
    if (errorParam) {
      setError(decodeURIComponent(errorParam))
    }
  }, [searchParams])

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-900">
      <div className="bg-gray-800 p-8 rounded-lg shadow-lg max-w-md w-full">
        <h1 className="text-2xl font-bold text-white mb-6 text-center">Login Required</h1>
        {error && (
          <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
            {error}
          </div>
        )}
        <SignIn /> {/* Handles GitHub login flow */}
        {!error && (
          <p className="mt-4 text-sm text-gray-400 text-center">
            You need to be logged in to edit story boundaries.
          </p>
        )}
      </div>
    </div>
  )
}

export default Login