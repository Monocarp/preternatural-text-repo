# Preternatural Mobile

Mobile-first PWA version of the Preternatural Text app.

## Setup

```bash
cd mobile
npm install
npm run dev
```

The app runs on port 5174 (separate from the main frontend on 5173).

## Features

- **Bottom tab navigation** - Archive, Search, Books, Account
- **Drill-down category navigation** - Tap to go deeper, swipe right to go back
- **Story cards** - Tap to open full-screen reader
- **Swipe gestures** - Right to go back, integrated with react-swipeable
- **PWA installable** - Add to home screen on mobile devices
- **Offline caching** - Service worker caches API responses

## Development

```bash
# Start dev server (with hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Testing on Mobile

1. Start the dev server: `npm run dev`
2. Make sure your phone is on the same network
3. Visit `http://<your-computer-ip>:5174` on your phone
4. In Chrome, tap menu → "Add to Home Screen"

## Project Structure

```
mobile/
├── src/
│   ├── App.tsx              # Routes configuration
│   ├── main.tsx             # Entry point
│   ├── store.ts             # Zustand state management
│   ├── components/
│   │   ├── MobileLayout.tsx # Bottom tab bar wrapper
│   │   └── StoryCard.tsx    # Reusable story card
│   ├── pages/
│   │   ├── ArchivePage.tsx  # Top-level categories
│   │   ├── CategoryPage.tsx # Drill-down navigation
│   │   ├── SearchPage.tsx   # Search with filters
│   │   ├── BooksPage.tsx    # Book archive
│   │   ├── AccountPage.tsx  # Auth & settings
│   │   └── StoryReaderPage.tsx # Full-screen reader
│   └── utils/
│       └── api.ts           # Axios client
├── public/                   # Static assets, icons
├── index.html
├── vite.config.ts           # PWA plugin config
└── package.json
```

## Backend API

Uses the same backend as the desktop frontend (`/api/*` endpoints).

Configure `VITE_API_URL` in `.env` for production.

## PWA Icons

You'll need to add icon files to `public/`:
- `icon-192.png` (192x192)
- `icon-512.png` (512x512)  
- `apple-touch-icon.png` (180x180)

Generate from your logo using a tool like https://realfavicongenerator.net/
