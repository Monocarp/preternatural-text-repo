// mobile/src/utils/api.ts
// Axios configuration with automatic token injection for Stack Auth
import axios from 'axios'
import { StackClientApp } from '@stackframe/react'

let appInstance: StackClientApp | null = null

export const setStackApp = (app: StackClientApp) => {
  appInstance = app
}

export const getStackApp = () => appInstance

// Helper to get access token from Stack Auth
const getAccessToken = async (): Promise<string | null> => {
  if (!appInstance) return null
  
  try {
    const user = await appInstance.getUser()
    if (!user) return null
    
    // Check cookies for Stack Auth tokens
    const cookies = document.cookie.split(';').reduce((acc, cookie) => {
      const [key, value] = cookie.trim().split('=')
      acc[key] = value
      return acc
    }, {} as Record<string, string>)
    
    // Stack Auth uses various cookie names
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
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important: include cookies in requests
})

// Request interceptor to add auth token
api.interceptors.request.use(
  async (config) => {
    const token = await getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      console.warn('Unauthorized request - user may need to log in')
    }
    return Promise.reject(error)
  }
)

export default api
