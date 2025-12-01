import { useNavigate } from 'react-router-dom'
import { useUser, useStackApp } from '@stackframe/react'

export default function AccountPage() {
  const user = useUser()
  const stackApp = useStackApp()
  const navigate = useNavigate()

  // Get display info
  const displayName = user?.displayName || user?.primaryEmail || 'User'
  const email = user?.primaryEmail || ''
  const initial = (displayName || email || 'U').charAt(0).toUpperCase()

  const handleSignIn = () => {
    sessionStorage.setItem('returnTo', '/account')
    navigate('/login')
  }

  const handleSignOut = async () => {
    await stackApp.signOut()
  }

  return (
    <div className="min-h-full bg-gray-900 pb-4">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 px-4 py-3 safe-area-top">
        <h1 className="text-xl font-bold text-white text-center">Account</h1>
      </header>

      {/* Content */}
      <div className="px-4 pt-6">
        {user ? (
          <div className="space-y-6">
            {/* User info */}
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 bg-blue-600 rounded-full flex items-center justify-center">
                  <span className="text-xl font-bold text-white">
                    {initial}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-medium truncate">{displayName}</p>
                  {email && displayName !== email && (
                    <p className="text-sm text-gray-400 truncate">{email}</p>
                  )}
                  <p className="text-sm text-green-400">Signed in</p>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-3">
              <button
                onClick={handleSignOut}
                className="w-full bg-gray-800 hover:bg-gray-700 active:bg-gray-600 border border-gray-700 rounded-xl p-4 text-left transition-colors"
              >
                <div className="flex items-center gap-3">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  <span className="text-white">Sign Out</span>
                </div>
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Sign in prompt */}
            <div className="text-center py-8">
              <div className="w-20 h-20 bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <h2 className="text-lg font-medium text-white mb-2">Not signed in</h2>
              <p className="text-gray-400 text-sm mb-6">
                Sign in to assign stories to categories and more.
              </p>
              <button
                onClick={handleSignIn}
                className="w-full max-w-xs mx-auto bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-medium py-3 px-6 rounded-xl transition-colors"
              >
                Sign In
              </button>
            </div>
          </div>
        )}

        {/* App info */}
        <div className="mt-8 pt-6 border-t border-gray-800">
          <div className="text-center text-gray-500 text-sm">
            <p>Preternatural Text</p>
            <p className="mt-1">Mobile v0.1.0</p>
          </div>
        </div>
      </div>
    </div>
  )
}
