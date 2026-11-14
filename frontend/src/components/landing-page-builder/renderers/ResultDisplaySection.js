import React from 'react';
import DOMPurify from 'dompurify';
import { CheckCircleIcon } from '@heroicons/react/24/outline';

export default function ResultDisplaySection({
  config,
  finalResult,
  executionStatus,
  previewMode,
}) {
  // In preview mode, show placeholder
  if (previewMode) {
    return (
      <div className="py-6">
        {config.title && (
          <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>
        )}
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-400 text-sm">{config.emptyMessage || 'Results will appear here after execution'}</p>
        </div>
      </div>
    );
  }

  // Show empty message if no result yet
  if (!finalResult) {
    const emptyMsg = config.emptyMessage || 'No results yet. Submit the form to see results.';
    return (
      <div className="py-6">
        {config.title && (
          <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>
        )}
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-400 text-sm">{emptyMsg}</p>
        </div>
      </div>
    );
  }

  const formatResult = (data) => {
    if (typeof data === 'string') {
      const trimmed = data.trim();
      const htmlTagPattern = /^<(!doctype html|html|div|span|p|h[1-6]|section|article|main|header|footer|nav|table|ul|ol|form|img)/i;
      if (htmlTagPattern.test(trimmed)) {
        return (
          <div
            className="w-full"
            dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(data) }}
          />
        );
      }
      return <div className="whitespace-pre-wrap break-words">{data}</div>;
    }
    if (typeof data === 'object') {
      return (
        <div className="max-h-[600px] overflow-y-auto">
          <pre className="whitespace-pre-wrap break-words text-sm font-mono bg-gray-50 p-4 rounded border border-gray-200">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      );
    }
    return <div className="whitespace-pre-wrap break-words">{String(data)}</div>;
  };

  const layoutClass = config.layout === 'full' ? '' : 'bg-white rounded-lg border border-gray-200 p-6';

  return (
    <div className="py-6">
      <div className="flex items-center gap-2 mb-4">
        {executionStatus === 'completed' && (
          <CheckCircleIcon className="w-5 h-5 text-green-600" />
        )}
        {config.title && (
          <h2 className="text-xl font-semibold text-gray-900">{config.title}</h2>
        )}
        {config.showTimestamp && (
          <span className="text-xs text-gray-400 ml-auto">
            {new Date().toLocaleTimeString()}
          </span>
        )}
      </div>
      <div className={layoutClass}>
        {formatResult(finalResult)}
      </div>
    </div>
  );
}
