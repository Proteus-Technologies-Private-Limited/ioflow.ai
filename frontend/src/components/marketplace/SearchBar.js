/**
 * SearchBar Component
 * Filter bar for marketplace (search is in header)
 */

import React, { useState } from 'react';
import { SlidersHorizontal, ChevronDown } from 'lucide-react';

const SearchBar = ({ filters, onFilterChange }) => {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSortChange = (e) => {
    onFilterChange({ ...filters, sort_by: e.target.value });
  };

  const handleBillingChange = (e) => {
    onFilterChange({ ...filters, billing_preference: e.target.value || null });
  };

  const handleMinRatingChange = (e) => {
    onFilterChange({ ...filters, min_rating: e.target.value ? parseFloat(e.target.value) : null });
  };

  const clearFilters = () => {
    onFilterChange({
      ...filters,
      min_rating: null,
      billing_preference: null,
      sort_by: 'popular',
      page: 1
    });
  };

  // Check if any filters are active
  const hasActiveFilters = filters.min_rating || filters.billing_preference || filters.sort_by !== 'popular';

  return (
    <div className="bg-white shadow-sm border-b border-gray-200 relative z-10">
      <div className="max-w-7xl mx-auto px-4 py-3">
        {/* Filter controls row */}
        <div className="flex items-center justify-between gap-4">
          {/* Left side: Sort dropdown (always visible) */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-600 hidden sm:block">Sort:</label>
            <select
              value={filters.sort_by || 'popular'}
              onChange={handleSortChange}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary focus:border-primary outline-none bg-white"
            >
              <option value="popular">Most Popular</option>
              <option value="recent">Recently Added</option>
              <option value="trending">Trending</option>
              <option value="rating">Highest Rated</option>
              <option value="price_low">Price: Low to High</option>
              <option value="price_high">Price: High to Low</option>
            </select>
          </div>

          {/* Right side: More filters toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-colors text-sm ${
              showAdvanced || hasActiveFilters
                ? 'bg-primary-10 border-primary text-primary'
                : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}
          >
            <SlidersHorizontal className="w-4 h-4" />
            <span>More Filters</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
            {hasActiveFilters && !showAdvanced && (
              <span className="w-2 h-2 bg-primary rounded-full"></span>
            )}
          </button>
        </div>

        {/* Advanced filters panel */}
        {showAdvanced && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Billing preference */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Pricing
                </label>
                <select
                  value={filters.billing_preference || ''}
                  onChange={handleBillingChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                >
                  <option value="">All</option>
                  <option value="free">Free</option>
                  <option value="per_user_per_month">Per User/Month</option>
                  <option value="per_execution">Per Execution</option>
                </select>
              </div>

              {/* Minimum rating */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Minimum Rating
                </label>
                <select
                  value={filters.min_rating || ''}
                  onChange={handleMinRatingChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                >
                  <option value="">All</option>
                  <option value="4">4+ Stars</option>
                  <option value="3">3+ Stars</option>
                  <option value="2">2+ Stars</option>
                  <option value="1">1+ Stars</option>
                </select>
              </div>

              {/* Clear filters button */}
              <div className="flex items-end">
                <button
                  onClick={clearFilters}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-100 transition-colors"
                >
                  Clear Filters
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchBar;
