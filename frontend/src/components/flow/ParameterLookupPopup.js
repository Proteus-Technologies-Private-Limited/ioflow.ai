import React, { useState, useEffect, useRef } from 'react';
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  ChevronUpDownIcon,
  CheckIcon,
  ArrowsUpDownIcon,
} from '@heroicons/react/24/outline';

const ParameterLookupPopup = ({
  isOpen,
  onClose,
  options = [],
  value,
  onSelect,
  placeholder = "Select an option...",
  loading = false,
  error = null,
  title = "Select Option"
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc', 'desc'
  const [sortBy, setSortBy] = useState('label'); // 'label', 'value'
  const [filteredOptions, setFilteredOptions] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  
  const searchInputRef = useRef(null);
  const popupRef = useRef(null);
  const optionsListRef = useRef(null);

  // Filter and sort options
  useEffect(() => {
    let filtered = options.filter(option =>
      option.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
      option.value.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Sort options
    filtered.sort((a, b) => {
      const aVal = sortBy === 'label' ? a.label : a.value;
      const bVal = sortBy === 'label' ? b.label : b.value;
      
      if (sortOrder === 'asc') {
        return aVal.localeCompare(bVal, undefined, { numeric: true, sensitivity: 'base' });
      } else {
        return bVal.localeCompare(aVal, undefined, { numeric: true, sensitivity: 'base' });
      }
    });

    setFilteredOptions(filtered);
    setSelectedIndex(-1);
  }, [options, searchTerm, sortOrder, sortBy]);

  // Focus search input when popup opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      setTimeout(() => {
        searchInputRef.current.focus();
      }, 100);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev => 
            prev < filteredOptions.length - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
          break;
        case 'Enter':
          e.preventDefault();
          if (selectedIndex >= 0 && filteredOptions[selectedIndex]) {
            handleSelect(filteredOptions[selectedIndex]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectedIndex, filteredOptions, onClose]);

  // Scroll selected option into view
  useEffect(() => {
    if (selectedIndex >= 0 && optionsListRef.current) {
      const selectedElement = optionsListRef.current.children[selectedIndex];
      if (selectedElement) {
        selectedElement.scrollIntoView({
          block: 'nearest',
          behavior: 'smooth'
        });
      }
    }
  }, [selectedIndex]);

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popupRef.current && !popupRef.current.contains(event.target)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen, onClose]);

  const handleSelect = (option) => {
    onSelect(option.value);
    onClose();
  };

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const clearSearch = () => {
    setSearchTerm('');
    searchInputRef.current?.focus();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
      <div
        ref={popupRef}
        className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[80vh] flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Search and Sort Controls */}
        <div className="p-4 border-b border-gray-200 space-y-3">
          {/* Search Input */}
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search options..."
              className="w-full pl-10 pr-8 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            {searchTerm && (
              <button
                onClick={clearSearch}
                className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Sort Controls */}
          <div className="flex items-center space-x-2 text-sm">
            <span className="text-gray-500">Sort by:</span>
            <button
              onClick={() => toggleSort('label')}
              className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                sortBy === 'label'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Label
              {sortBy === 'label' && (
                <ArrowsUpDownIcon className={`w-3 h-3 ml-1 ${sortOrder === 'desc' ? 'rotate-180' : ''}`} />
              )}
            </button>
            <button
              onClick={() => toggleSort('value')}
              className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                sortBy === 'value'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Value
              {sortBy === 'value' && (
                <ArrowsUpDownIcon className={`w-3 h-3 ml-1 ${sortOrder === 'desc' ? 'rotate-180' : ''}`} />
              )}
            </button>
          </div>
        </div>

        {/* Options List */}
        <div className="flex-1 overflow-hidden">
          {loading && (
            <div className="flex items-center justify-center p-8 text-gray-500">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <span className="ml-3">Loading options...</span>
            </div>
          )}

          {error && (
            <div className="p-4 text-red-600 bg-red-50 text-center">
              <p className="font-medium">Error loading options</p>
              <p className="text-sm mt-1">{error}</p>
            </div>
          )}

          {!loading && !error && (
            <>
              {filteredOptions.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  {searchTerm ? (
                    <>
                      <p>No options match "{searchTerm}"</p>
                      <button
                        onClick={clearSearch}
                        className="mt-2 text-blue-600 hover:text-blue-800 text-sm underline"
                      >
                        Clear search
                      </button>
                    </>
                  ) : (
                    <p>No options available</p>
                  )}
                </div>
              ) : (
                <div
                  ref={optionsListRef}
                  className="max-h-80 overflow-y-auto"
                >
                  {filteredOptions.map((option, index) => (
                    <button
                      key={option.value}
                      onClick={() => handleSelect(option)}
                      className={`w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0 flex items-center justify-between ${
                        index === selectedIndex ? 'bg-blue-50' : ''
                      } ${
                        value === option.value ? 'bg-blue-100' : ''
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 truncate">
                          {option.label}
                        </div>
                        {option.label !== option.value && (
                          <div className="text-sm text-gray-500 truncate mt-1">
                            {option.value}
                          </div>
                        )}
                      </div>
                      {value === option.value && (
                        <CheckIcon className="w-5 h-5 text-blue-600 flex-shrink-0 ml-2" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50 text-sm text-gray-600 flex items-center justify-between">
          <span>
            {filteredOptions.length} of {options.length} options
          </span>
          <div className="flex items-center space-x-4 text-xs">
            <span>↑↓ Navigate</span>
            <span>Enter Select</span>
            <span>Esc Close</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ParameterLookupPopup;