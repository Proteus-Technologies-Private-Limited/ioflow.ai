import React, { useState } from 'react';

const InputForm = ({ onSubmit, isLoading, disabled }) => {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSubmit(input);
      setInput('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mb-6">
      <label htmlFor="user-input" className="block text-sm font-medium text-gray-700 mb-2">
        Your Input
      </label>
      <div className="flex gap-2">
        <textarea
          id="user-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter your request here..."
          disabled={disabled || isLoading}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          rows="4"
        />
        <button
          type="submit"
          disabled={disabled || isLoading || !input.trim()}
          className="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors self-end"
        >
          {isLoading ? (
            <span className="flex items-center">
              <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Processing...
            </span>
          ) : (
            'Submit'
          )}
        </button>
      </div>
    </form>
  );
};

export default InputForm;