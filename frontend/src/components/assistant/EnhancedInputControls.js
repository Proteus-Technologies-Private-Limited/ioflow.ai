import React, { forwardRef, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PaperAirplaneIcon,
  StopCircleIcon,
  CommandLineIcon
} from '@heroicons/react/24/solid';
import { NAVIGATION_DICTIONARY, findMatchingPages } from './NavigationHandler';

const EnhancedInputControls = forwardRef(({
  value,
  onChange,
  onSend,
  onCancel,
  onKeyDown: parentKeyDown,
  isStreaming,
  disabled,
  placeholder
}, ref) => {
  const textareaRef = useRef(null);
  const navigate = useNavigate();
  const [suggestions, setSuggestions] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Combine refs
  useEffect(() => {
    if (ref) {
      ref.current = textareaRef.current;
    }
  }, [ref]);

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const scrollHeight = textarea.scrollHeight;
      const minHeight = 44;
      const maxHeight = 200;
      const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
      textarea.style.height = `${newHeight}px`;

      if (scrollHeight > maxHeight) {
        textarea.style.overflowY = 'auto';
      } else {
        textarea.style.overflowY = 'hidden';
      }
    }
  }, [value]);

  // Update suggestions when input changes
  useEffect(() => {
    if (value && value.trim()) {
      const matches = findMatchingPages(value);
      if (matches.length > 0) {
        setSuggestions(matches.slice(0, 5));
        setShowSuggestions(true);
        setSelectedIndex(-1);
      } else {
        setSuggestions([]);
        setShowSuggestions(false);
      }
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
      setSelectedIndex(-1);
    }
  }, [value]);

  // Navigate to a page
  const handleNavigate = (page) => {
    console.log(`Navigating to ${page.path}: ${page.description}`);
    navigate(page.path);
    onChange(''); // Clear input
    setShowSuggestions(false);
    setSuggestions([]);
    // Don't add to chat history
  };

  const handleKeyDown = (e) => {
    // Handle navigation-specific keys
    if (showSuggestions) {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev =>
            prev < suggestions.length - 1 ? prev + 1 : prev
          );
          return;

        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev => prev > -1 ? prev - 1 : -1);
          return;

        case 'Tab':
          e.preventDefault();
          if (suggestions.length > 0) {
            const index = selectedIndex >= 0 ? selectedIndex : 0;
            handleNavigate(suggestions[index]);
          }
          return;

        case 'Escape':
          e.preventDefault();
          setShowSuggestions(false);
          setSelectedIndex(-1);
          return;
      }
    }

    // Handle Enter key
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();

      // If suggestion is selected, navigate
      if (showSuggestions && selectedIndex >= 0 && suggestions[selectedIndex]) {
        handleNavigate(suggestions[selectedIndex]);
        return;
      }

      // Check for exact/high-confidence navigation match
      const trimmedInput = value.trim().toLowerCase();
      const matches = findMatchingPages(trimmedInput);

      if (matches.length > 0 && matches[0].score >= 80) {
        // High confidence navigation match
        handleNavigate(matches[0]);
        return;
      }

      // Not a navigation command, send as normal message
      onSend();
    }

    // Call parent's keydown handler for other cases
    if (parentKeyDown) {
      parentKeyDown(e);
    }
  };

  const handleSendClick = () => {
    // Check if this might be a navigation command
    const trimmedInput = value.trim().toLowerCase();
    const matches = findMatchingPages(trimmedInput);

    if (matches.length > 0 && matches[0].score >= 80) {
      // High confidence navigation match
      handleNavigate(matches[0]);
      return;
    }

    // Normal send
    onSend();
  };

  return (
    <div className="relative">
      {/* Navigation suggestions */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-lg shadow-lg border border-gray-200 max-h-60 overflow-y-auto z-50">
          <div className="p-2">
            <div className="text-xs text-gray-500 px-2 py-1 flex items-center gap-1 border-b mb-1">
              <CommandLineIcon className="h-3 w-3" />
              Quick Navigation - Press Enter to navigate
            </div>
            {suggestions.map((suggestion, index) => (
              <button
                key={suggestion.key}
                onClick={() => handleNavigate(suggestion)}
                onMouseEnter={() => setSelectedIndex(index)}
                className={`
                  w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                  ${index === selectedIndex
                    ? 'bg-primary-10 text-primary'
                    : 'hover:bg-gray-50 text-gray-700'
                  }
                `}
              >
                <div className="font-medium">
                  {suggestion.description.split(' - ')[0]}
                </div>
                <div className="text-xs text-gray-500">
                  {suggestion.description.split(' - ')[1]}
                </div>
              </button>
            ))}
            <div className="text-xs text-gray-400 px-2 py-1 mt-1 border-t">
              Use ↑↓ to navigate • Tab to select first • Esc to close
            </div>
          </div>
        </div>
      )}

      {/* Input controls */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || "Type a page name to navigate or ask a question..."}
          disabled={disabled || isStreaming}
          className="flex-1 resize-none px-3 py-2.5 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary disabled:bg-gray-50 disabled:text-gray-500 transition-all duration-150"
          style={{
            minHeight: '44px',
            maxHeight: '200px',
            overflowY: 'hidden'
          }}
          rows={1}
        />
        {isStreaming ? (
          <button
            onClick={onCancel}
            className="h-[44px] w-[44px] bg-red-600 hover:bg-red-700 text-white rounded-md flex items-center justify-center transition-colors flex-shrink-0"
          >
            <StopCircleIcon className="h-5 w-5" />
          </button>
        ) : (
          <button
            onClick={handleSendClick}
            disabled={disabled || !value.trim()}
            className="h-[44px] w-[44px] bg-gradient-primary hover:shadow-lg disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-md flex items-center justify-center transition-all flex-shrink-0"
          >
            <PaperAirplaneIcon className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
});

EnhancedInputControls.displayName = 'EnhancedInputControls';

export default EnhancedInputControls;