import React from 'react';

interface SearchBarProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
  categories: string[];
  inStockOnly: boolean;
  onInStockToggle: (checked: boolean) => void;
  language?: 'en' | 'hi';
}

export const SearchBar: React.FC<SearchBarProps> = ({
  searchTerm,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  categories,
  inStockOnly,
  onInStockToggle,
  language = 'en',
}) => {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm mb-6">
      <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center">
        {/* Search Input */}
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={
              language === 'hi'
                ? 'उत्पाद या SKU खोजें (जैसे Biscuit, Detergent, चाय)...'
                : 'Search products or SKU (e.g., Biscuit, Detergent, Tea)...'
            }
            className="w-full pl-10 pr-10 py-2.5 bg-gray-50 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
          />
          {searchTerm && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-gray-400 hover:text-gray-600"
              title="Clear search"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Category Filter */}
        <div className="w-full md:w-56">
          <select
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="w-full py-2.5 px-3 bg-gray-50 border border-gray-300 rounded-xl text-sm font-medium text-gray-700 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="all">
              {language === 'hi' ? 'सभी श्रेणियां (All Categories)' : 'All Categories'}
            </option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {/* In-Stock Toggle */}
        <label className="flex items-center gap-2 cursor-pointer select-none px-3 py-2 bg-gray-50 border border-gray-300 rounded-xl hover:bg-gray-100 transition-colors">
          <input
            type="checkbox"
            checked={inStockOnly}
            onChange={(e) => onInStockToggle(e.target.checked)}
            className="w-4 h-4 text-primary-600 rounded border-gray-300 focus:ring-primary-500"
          />
          <span className="text-xs font-bold text-gray-700 whitespace-nowrap">
            {language === 'hi' ? 'केवल उपलब्ध स्टॉक (In Stock)' : 'In-Stock Only'}
          </span>
        </label>
      </div>
    </div>
  );
};

export default SearchBar;
