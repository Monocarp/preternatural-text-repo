import { useState, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

const VIDEO_FILES = [
  '/Best.mp4',
  '/Branches Light.mp4',
  '/Growth.mp4',
  '/Intro.mp4',
  '/Lots of leaves.mp4',
  '/MYstical.mp4',
  '/No fire.mp4',
]

export default function Home() {
  const [videoEnded, setVideoEnded] = useState(false)
  const [isMuted, setIsMuted] = useState(true)
  const videoRef = useRef<HTMLVideoElement>(null)
  const navigate = useNavigate()

  // Pick a random video on component mount
  const videoSrc = useMemo(() => {
    return VIDEO_FILES[Math.floor(Math.random() * VIDEO_FILES.length)]
  }, [])

  const handleVideoEnd = () => {
    setVideoEnded(true)
  }

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !videoRef.current.muted
      setIsMuted(videoRef.current.muted)
    }
  }

  const buttons = [
    { label: 'Book Archive', path: '/book-archive' },
    { label: 'Story Archive', path: '/archive' },
    { label: 'Search & Curate', path: '/search-curate' },
  ]

  return (
    <div className="fixed inset-0 bg-gray-950 flex items-center justify-center overflow-hidden">
      {/* Video — fills the screen */}
      <video
        ref={videoRef}
        src={videoSrc}
        autoPlay
        muted
        playsInline
        onEnded={handleVideoEnd}
        className="min-h-screen min-w-full object-cover"
      />

      {/* Buttons — overlay at the bottom, fade in after video ends */}
      <div
        className={`absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-3 px-6 transition-all duration-1000 ease-out ${
          videoEnded
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 translate-y-6 pointer-events-none'
        }`}
      >
        {buttons.map((btn) => (
          <button
            key={btn.path}
            onClick={() => navigate(btn.path)}
            className="py-2 px-4 rounded-md text-sm font-medium transition-all duration-200
              bg-gray-800/80 border border-gray-600/60 text-gray-200 backdrop-blur-sm
              hover:bg-gray-700 hover:border-gray-500 hover:text-white hover:shadow-lg hover:shadow-amber-900/10
              active:scale-[0.98]"
          >
            {btn.label}
          </button>
        ))}
      </div>

      {/* Audio toggle button - always visible */}
      <button
        onClick={toggleMute}
        className="absolute bottom-8 right-8 p-2 rounded-md transition-all duration-200
          bg-gray-800/80 border border-gray-600/60 text-gray-200 backdrop-blur-sm
          hover:bg-gray-700 hover:border-gray-500 hover:text-white
          active:scale-[0.98]"
        title={isMuted ? 'Unmute' : 'Mute'}
      >
        {isMuted ? (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
          </svg>
        )}
      </button>
    </div>
  )
}
