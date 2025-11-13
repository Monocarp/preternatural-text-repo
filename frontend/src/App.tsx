import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <Router>
      <div className="flex">
        {/* Sidebar placeholder */}
        <aside className="w-64 bg-gray-100 p-4">Sidebar Tree Here</aside>
        <main className="flex-1 p-4">
          <Routes>
            <Route path="/" element={<div>Welcome to Story Archive</div>} />
            <Route path="/search-curate" element={<div>Search & Curate Page</div>} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;