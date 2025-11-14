// src/components/Login.tsx
import { useState } from 'react'
import { useStore } from '../store' // If using for user state

const Login = () => {
  const [loading, setLoading] = useState(false)

  const loginWithGitHub = () => {
    setLoading(true)
    window.location.href = 'https://auth.neon.tech/authorize?provider=github&redirect_uri=http://localhost:5173/callback'  // Change to your domain in prod
  }

  return (
    <button onClick={loginWithGitHub} disabled={loading} className="bg-blue-500 text-white px-4 py-2">
      {loading ? 'Logging in...' : 'Login with GitHub'}
    </button>
  )
}

export default Login