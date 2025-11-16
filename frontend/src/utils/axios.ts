// frontend/src/utils/axios.ts
// Axios configuration with automatic token injection for Stack Auth
import axios from 'axios'
import { StackClientApp } from '@stackframe/react'

let appInstance: StackClientApp | null = null

export const setStackApp = (app: StackClientApp) => {
  appInstance = app
}

// Helper to get access token from Stack Auth
// Stack Auth stores tokens in cookies when tokenStore: 'cookie' is used
// We need to access the user session to get the token
const getAccessToken = async (): Promise<string | null> => {
  if (!appInstance) return null
  
  try {
    // Stack Auth typically provides token through user session
    // Since cookies are used, the token might be accessible via the user object
    // Or we may need to read from cookies directly
    const user = await appInstance.getUser()
    if (!user) return null
    
    // Try to get token from user session or cookies
    // Stack Auth with cookie storage should make tokens available in requests automatically
    // But for explicit token access, we may need to check cookies
    // For now, return null and let Stack Auth handle it via cookies
    // The backend should accept tokens from Authorization header OR cookies
    
    // Check if there's a way to get the token directly
    // Stack Auth may expose it differently - check cookies as fallback
    const cookies = document.cookie.split(';').reduce((acc, cookie) => {
      const [key, value] = cookie.trim().split('=')
      acc[key] = value
      return acc
    }, {} as Record<string, string>)
    
    // Stack Auth typically uses cookie names like 'stack-access-token' or similar
    // Check common cookie names
    const projectId = (appInstance as any).projectId || ''
    return cookies['stack-access-token'] || 
           cookies['stack_token'] || 
           (projectId ? cookies[`stack-${projectId}-access-token`] : null) ||
           null
  } catch (error) {
    console.debug('Could not get access token:', error)
    return null
  }
}

// Create axios instance
const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important: include cookies in requests
})

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  async (config) => {
    // Try to get token and add to Authorization header
    const token = await getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // Even without explicit token, cookies will be sent via withCredentials
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    // If 401 Unauthorized, redirect to login
    if (error.response?.status === 401) {
      if (appInstance) {
        try {
          const user = await appInstance.getUser()
          if (!user) {
            // Not logged in, redirect to login
            const returnTo = window.location.pathname + window.location.search
            sessionStorage.setItem('returnTo', returnTo)
            window.location.href = '/login'
          }
        } catch (err) {
          console.error('Error checking auth state:', err)
        }
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient

