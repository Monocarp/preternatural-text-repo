import { useState, useRef, useEffect } from "react";

interface SubcategoryFilterProps {
  subcategories: string[];
  selectedSubcats: string[];
  onFilterChange: (selected: string[]) => void;
}

export function SubcategoryFilter(props: SubcategoryFilterProps) {
  const { subcategories, selectedSubcats, onFilterChange } = props;
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

  // Render nothing if subcategories array is empty
  if (subcategories.length === 0) {
    return <></>;
  }

  const handleCheckboxChange = (subcat: string, checked: boolean) => {
    let updatedSelection;
    if (checked) {
      updatedSelection = [...selectedSubcats, subcat];
    } else {
      updatedSelection = selectedSubcats.filter((s) => s !== subcat);
    }
    onFilterChange(updatedSelection);
  };

  const handleClearFilters = () => {
    onFilterChange([]);
  };

  const buttonLabel = selectedSubcats.length === 0 
    ? "Filter by subcategory" 
    : `${selectedSubcats.length} subcategor${selectedSubcats.length === 1 ? 'y' : 'ies'} selected`;

  return (
    <div className="relative mb-4" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full sm:w-auto min-w-[220px] px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm hover:bg-gray-700 transition-colors"
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
        <div className="absolute z-10 mt-1 w-full sm:w-auto min-w-[220px] bg-gray-800 border border-gray-600 rounded-lg shadow-lg">
          <div className="max-h-60 overflow-y-auto p-2">
            {subcategories.map((subcat) => (
              <label 
                key={subcat} 
                className="flex items-center px-2 py-1.5 hover:bg-gray-700 rounded cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedSubcats.includes(subcat)}
                  onChange={(e) => handleCheckboxChange(subcat, e.target.checked)}
                  className="rounded border-gray-600 bg-gray-700 text-blue-500 mr-2 focus:ring-blue-500 focus:ring-offset-gray-800"
                />
                <span className="text-gray-200 text-sm">{subcat}</span>
              </label>
            ))}
          </div>
          {selectedSubcats.length > 0 && (
            <div className="border-t border-gray-600 p-2">
              <button
                onClick={handleClearFilters}
                className="w-full text-blue-400 hover:text-blue-300 text-xs py-1"
              >
                Clear all filters
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}