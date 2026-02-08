import { useState, useRef, useEffect } from "react";

interface Book {
  id: number;
  slug: string;
  title: string;
  author: string;
  year: number;
  story_count: number;
}

interface BookFilterProps {
  books: Book[];
  selectedBookSlug: string | null;
  onFilterChange: (bookSlug: string | null) => void;
}

export function BookFilter(props: BookFilterProps) {
  const { books, selectedBookSlug, onFilterChange } = props;
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Render nothing if books array is empty
  if (books.length === 0) {
    return <></>;
  }

  const handleBookSelect = (bookSlug: string | null) => {
    onFilterChange(bookSlug);
    setIsOpen(false);
  };

  const selectedBook = books.find(b => b.slug === selectedBookSlug);
  const buttonLabel = selectedBook
    ? selectedBook.title
    : "All Books";

  return (
    <div className="relative mb-4" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm active:bg-gray-700"
      >
        <span>{buttonLabel}</span>
        <svg 
          className={`ml-2 w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute z-10 mt-1 w-full bg-gray-800 border border-gray-600 rounded-lg shadow-lg">
          <div className="max-h-60 overflow-y-auto p-2">
            {/* Option for "All Books" */}
            <button
              onClick={() => handleBookSelect(null)}
              className={`w-full text-left px-2 py-1.5 active:bg-gray-700 rounded text-sm ${
                selectedBookSlug === null ? 'bg-gray-700 text-blue-400' : 'text-gray-200'
              }`}
            >
              All Books
            </button>
            
            {/* Individual book options */}
            {books.map((book) => (
              <button
                key={book.slug}
                onClick={() => handleBookSelect(book.slug)}
                className={`w-full text-left px-2 py-1.5 active:bg-gray-700 rounded text-sm ${
                  selectedBookSlug === book.slug ? 'bg-gray-700 text-blue-400' : 'text-gray-200'
                }`}
              >
                {book.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
