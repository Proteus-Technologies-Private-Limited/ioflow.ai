import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ExclamationTriangleIcon, XCircleIcon, InformationCircleIcon, ArrowPathIcon } from '@heroicons/react/24/solid';

const ValidationErrorTooltip = ({ errors = [], className = "", onRevalidate }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const [isRevalidating, setIsRevalidating] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const indicatorRef = useRef(null);
  const tooltipRef = useRef(null);
  
  if (!errors || errors.length === 0) return null;
  
  // Categorize errors
  const criticalErrors = errors.filter(e => e.type === 'error');
  const warnings = errors.filter(e => e.type === 'warning');
  const info = errors.filter(e => e.type === 'info');
  
  const hasCriticalErrors = criticalErrors.length > 0;
  const hasWarnings = warnings.length > 0;
  
  // Determine the indicator color and icon
  const getIndicatorStyle = () => {
    if (hasCriticalErrors) {
      return {
        bgColor: 'bg-red-500',
        borderColor: 'border-red-500',
        icon: <XCircleIcon className="w-4 h-4 text-red-500" />
      };
    } else if (hasWarnings) {
      return {
        bgColor: 'bg-yellow-500',
        borderColor: 'border-yellow-500',
        icon: <ExclamationTriangleIcon className="w-4 h-4 text-yellow-600" />
      };
    } else {
      return {
        bgColor: 'bg-blue-500',
        borderColor: 'border-blue-500',
        icon: <InformationCircleIcon className="w-4 h-4 text-blue-500" />
      };
    }
  };
  
  const { bgColor, borderColor, icon } = getIndicatorStyle();
  
  const handleRevalidate = async () => {
    if (onRevalidate) {
      setIsRevalidating(true);
      try {
        await onRevalidate();
      } finally {
        setIsRevalidating(false);
      }
    }
  };
  
  // Calculate tooltip position when showing
  useEffect(() => {
    if (showTooltip && indicatorRef.current) {
      const rect = indicatorRef.current.getBoundingClientRect();
      const tooltipWidth = 400;
      const tooltipHeight = 500; // Max height
      
      // Calculate position - try to show to the right and above
      let left = rect.right + 10;
      let top = rect.top - 100;
      
      // Check if it would go off the right edge of screen
      if (left + tooltipWidth > window.innerWidth) {
        // Show to the left instead
        left = rect.left - tooltipWidth - 10;
      }
      
      // Check if it would go off the left edge
      if (left < 10) {
        left = 10;
      }
      
      // Check if it would go above the top
      if (top < 10) {
        top = rect.bottom + 10;
      }
      
      // Check if it would go below the bottom
      if (top + tooltipHeight > window.innerHeight) {
        top = window.innerHeight - tooltipHeight - 10;
      }
      
      setTooltipPosition({
        top: top,
        left: left
      });
    }
  }, [showTooltip]);
  
  // Close tooltip on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && showTooltip) {
        setShowTooltip(false);
      }
    };
    
    if (showTooltip) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [showTooltip]);
  
  // Tooltip content as a portal
  const tooltipContent = showTooltip && createPortal(
    <div 
      ref={tooltipRef}
      className="fixed z-[9999] min-w-[350px] max-w-[500px]"
      style={{ 
        top: `${tooltipPosition.top}px`, 
        left: `${tooltipPosition.left}px`,
        pointerEvents: 'auto'
      }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className={`bg-white rounded-lg shadow-2xl border-2 ${borderColor} overflow-hidden`}>
            {/* Header */}
            <div className={`bg-gray-50 border-b px-4 py-3 flex items-center justify-between`}>
              <div className="flex items-center gap-2">
                {icon}
                <span className="font-semibold text-gray-800 text-base">
                  Validation Issues ({errors.length})
                </span>
              </div>
              <div className="flex items-center gap-2">
                {onRevalidate && (
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRevalidate();
                    }}
                    disabled={isRevalidating}
                    className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Revalidate flow"
                  >
                    <ArrowPathIcon className={`w-3 h-3 ${isRevalidating ? 'animate-spin' : ''}`} />
                    {isRevalidating ? 'Validating...' : 'Revalidate'}
                  </button>
                )}
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowTooltip(false);
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            
            {/* Error list */}
            <div className="max-h-[400px] overflow-y-auto">
              {criticalErrors.length > 0 && (
                <div className="p-4 border-b">
                  <div className="flex items-center gap-2 mb-3">
                    <XCircleIcon className="w-5 h-5 text-red-500" />
                    <span className="font-semibold text-red-700 text-sm">Errors</span>
                  </div>
                  <div className="space-y-3">
                    {criticalErrors.map((error, idx) => (
                      <div key={idx} className="bg-red-50 border border-red-200 rounded-lg p-3">
                        <p className="text-red-800 font-medium text-sm mb-2">
                          {error.message}
                        </p>
                        {error.field && (
                          <p className="text-red-600 text-xs mb-1">
                            Field: <code className="bg-red-100 px-1 py-0.5 rounded">{error.field}</code>
                          </p>
                        )}
                        {error.suggestion && (
                          <div className="mt-2 pt-2 border-t border-red-200">
                            <p className="text-gray-700 text-xs font-medium mb-1">💡 How to fix:</p>
                            <p className="text-gray-600 text-xs leading-relaxed">
                              {error.suggestion}
                            </p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {warnings.length > 0 && (
                <div className="p-4 border-b">
                  <div className="flex items-center gap-2 mb-3">
                    <ExclamationTriangleIcon className="w-5 h-5 text-yellow-600" />
                    <span className="font-semibold text-yellow-700 text-sm">Warnings</span>
                  </div>
                  <div className="space-y-3">
                    {warnings.map((warning, idx) => (
                      <div key={idx} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                        <p className="text-yellow-800 font-medium text-sm mb-2">
                          {warning.message}
                        </p>
                        {warning.field && (
                          <p className="text-yellow-600 text-xs mb-1">
                            Field: <code className="bg-yellow-100 px-1 py-0.5 rounded">{warning.field}</code>
                          </p>
                        )}
                        {warning.suggestion && (
                          <div className="mt-2 pt-2 border-t border-yellow-200">
                            <p className="text-gray-700 text-xs font-medium mb-1">💡 Suggestion:</p>
                            <p className="text-gray-600 text-xs leading-relaxed">
                              {warning.suggestion}
                            </p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {info.length > 0 && (
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <InformationCircleIcon className="w-5 h-5 text-blue-500" />
                    <span className="font-semibold text-blue-700 text-sm">Information</span>
                  </div>
                  <div className="space-y-3">
                    {info.map((item, idx) => (
                      <div key={idx} className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                        <p className="text-blue-800 font-medium text-sm">
                          {item.message}
                        </p>
                        {item.suggestion && (
                          <p className="text-blue-600 text-xs mt-1">
                            {item.suggestion}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            {/* Footer with quick actions */}
            <div className="bg-gray-50 border-t px-4 py-3">
              <p className="text-xs text-gray-500">
                {hasCriticalErrors ? 
                  "⚠️ Fix errors before the flow can be executed properly." :
                  hasWarnings ? 
                    "⚡ Flow will work but consider addressing warnings." :
                    "ℹ️ Review these suggestions to improve your flow."
                }
              </p>
            </div>
          </div>
        </div>,
    document.body
  );
  
  return (
    <>
      <div className={`relative ${className}`}>
        {/* Error indicator dot */}
        <div 
          ref={indicatorRef}
          className={`w-3 h-3 rounded-full ${bgColor} cursor-pointer animate-pulse`}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          onClick={() => setShowTooltip(!showTooltip)}
        />
      </div>
      {/* Render tooltip as portal */}
      {tooltipContent}
    </>
  );
};

export default ValidationErrorTooltip;