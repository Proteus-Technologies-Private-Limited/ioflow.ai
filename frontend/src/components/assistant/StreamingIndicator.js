import React from 'react';
import { SparklesIcon } from '@heroicons/react/24/outline';

function StreamingIndicator() {
  return (
    <div className="flex gap-3 mb-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
        <SparklesIcon className="h-5 w-5" />
      </div>
      <div className="max-w-[80%] rounded-lg p-3 bg-gray-100">
        <div className="flex items-center gap-2">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
          <span className="text-sm text-gray-600">Thinking...</span>
        </div>
      </div>
    </div>
  );
}

export default StreamingIndicator;