// src/pages/Callback.tsx
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
// # import jwtDecode from 'jwt-decode'
import { jwtDecode } from 'jwt-decode'

const Callback = () => {
  const navigate = useNavigate()

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token') // Adjust if Neon uses different param
    if (token) {
      localStorage.setItem('token', token)
      const decoded = jwtDecode(token)
      navigate('/')
    } else {
      navigate('/login')
    }
  }, [])

  return <div>Authenticating...</div>
}

export default Callback