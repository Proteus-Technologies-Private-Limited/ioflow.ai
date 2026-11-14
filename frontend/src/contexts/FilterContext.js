import React, { createContext, useContext, useState, useEffect } from 'react';

// Create the FilterContext
const FilterContext = createContext();

// Custom hook to use the FilterContext
export const useFilters = () => {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error('useFilters must be used within a FilterProvider');
  }
  return context;
};

// FilterProvider component
export const FilterProvider = ({ children }) => {
  // Store filters for different pages
  const [filters, setFilters] = useState(() => {
    // Load saved filters from localStorage on initial load
    const savedFilters = localStorage.getItem('ioflow_filters');
    return savedFilters ? JSON.parse(savedFilters) : {};
  });

  // Save filters to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('ioflow_filters', JSON.stringify(filters));
  }, [filters]);

  // Update filters for a specific page
  const updatePageFilters = (pageName, pageFilters) => {
    setFilters(prev => ({
      ...prev,
      [pageName]: pageFilters
    }));
  };

  // Get filters for a specific page
  const getPageFilters = (pageName, defaultFilters = {}) => {
    return filters[pageName] || defaultFilters;
  };

  // Clear filters for a specific page
  const clearPageFilters = (pageName) => {
    setFilters(prev => {
      const newFilters = { ...prev };
      delete newFilters[pageName];
      return newFilters;
    });
  };

  // Clear all filters
  const clearAllFilters = () => {
    setFilters({});
    localStorage.removeItem('ioflow_filters');
  };

  const value = {
    filters,
    updatePageFilters,
    getPageFilters,
    clearPageFilters,
    clearAllFilters
  };

  return (
    <FilterContext.Provider value={value}>
      {children}
    </FilterContext.Provider>
  );
};

export default FilterContext;