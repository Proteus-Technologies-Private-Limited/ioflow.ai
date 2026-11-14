import React from 'react';
import { PlusIcon } from '@heroicons/react/24/outline';

/**
 * QuickVariableButton Component
 * A small + button that appears next to input fields for quick variable selection
 * Matches Zapier's UX pattern of always-visible variable access
 */
const QuickVariableButton = ({
  onClick,
  disabled = false,
  size = 'md', // 'sm', 'md', 'lg'
  tooltip = 'Insert data from previous steps'
}) => {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-10 h-10'
  };

  const iconSizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5'
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={tooltip}
      className={`
        ${sizeClasses[size]}
        inline-flex items-center justify-center
        rounded-md border border-gray-300
        bg-white hover:bg-gray-50
        text-gray-600 hover:text-blue-600
        hover:border-blue-400
        transition-all duration-150
        disabled:opacity-50 disabled:cursor-not-allowed
        shadow-sm hover:shadow
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      `}
    >
      <PlusIcon className={iconSizeClasses[size]} />
    </button>
  );
};

export default QuickVariableButton;
