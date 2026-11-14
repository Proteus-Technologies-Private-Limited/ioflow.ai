import React from 'react';
import { InformationCircleIcon } from '@heroicons/react/24/outline';

const JsonErrorTooltip = ({ error }) => {
  const [isVisible, setIsVisible] = React.useState(false);
  
  // Parse JSON string errors to provide better context
  const getErrorContext = () => {
    if (!error || !error.message) return null;
    
    // Check for JSON parsing errors
    const jsonErrorMatch = error.message.match(/Invalid JSON string: (.+) at position (\d+)/);
    if (jsonErrorMatch) {
      const [, errorMsg, position] = jsonErrorMatch;
      return {
        type: 'json',
        message: errorMsg,
        position: parseInt(position, 10)
      };
    }
    
    // Check for type mismatch errors
    const typeErrorMatch = error.message.match(/'(.+)' is not of type '(.+)'/);
    if (typeErrorMatch) {
      const [, value, expectedType] = typeErrorMatch;
      return {
        type: 'type',
        value: value.substring(0, 50) + (value.length > 50 ? '...' : ''),
        expectedType
      };
    }
    
    return null;
  };
  
  const context = getErrorContext();
  
  if (!context) return null;
  
  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        className="ml-2 text-gray-400 hover:text-gray-600"
      >
        <InformationCircleIcon className="h-4 w-4" />
      </button>
      
      {isVisible && (
        <div className="absolute z-10 w-64 px-3 py-2 text-sm text-white bg-gray-900 rounded-lg shadow-lg -top-2 left-6">
          <div className="absolute w-0 h-0 border-t-4 border-b-4 border-r-4 border-transparent border-r-gray-900 -left-1 top-3"></div>
          
          {context.type === 'json' && (
            <>
              <p className="font-semibold mb-1">JSON Parse Error</p>
              <p className="text-gray-300">Error: {context.message}</p>
              <p className="text-gray-300">Position: Character {context.position}</p>
              <p className="text-gray-400 text-xs mt-1">
                Tip: Check for missing quotes, commas, or brackets
              </p>
            </>
          )}
          
          {context.type === 'type' && (
            <>
              <p className="font-semibold mb-1">Type Mismatch</p>
              <p className="text-gray-300">Expected: {context.expectedType}</p>
              <p className="text-gray-300">Got: {context.value}</p>
              <p className="text-gray-400 text-xs mt-1">
                Tip: Ensure the value matches the expected type
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default JsonErrorTooltip;