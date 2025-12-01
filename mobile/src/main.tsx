import React from 'react'
import ReactDOM from 'react-dom/client'
import { StackProvider, StackClientApp, StackTheme } from '@stackframe/react'
import App from './App'
import { setStackApp } from './utils/api'
import './index.css'

// Load from environment
const projectId = import.meta.env.VITE_STACK_PROJECT_ID
const publishableKey = import.meta.env.VITE_STACK_PUBLISHABLE_CLIENT_KEY

// Create the StackClientApp instance
const stackApp = new StackClientApp({
  projectId,
  publishableClientKey: publishableKey,
  tokenStore: 'cookie'  // Required for client-side persistence
})

// Register app instance with axios interceptor
setStackApp(stackApp)

// Export for use in components
export { stackApp }

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <StackProvider app={stackApp}>
      <StackTheme>
        <App />
      </StackTheme>
    </StackProvider>
  </React.StrictMode>
)
