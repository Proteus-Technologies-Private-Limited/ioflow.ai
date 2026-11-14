import React from 'react';
import {
  CursorArrowRaysIcon,
  CodeBracketIcon,
  CalculatorIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  GlobeAltIcon,
  XMarkIcon,
  PencilIcon,
} from '@heroicons/react/24/outline';

/**
 * VariablePill Component
 * Displays variable references as visual pills with icons and friendly labels
 *
 * Example inputs:
 * - "input.email" → [Trigger Icon] Trigger Data • email
 * - "node_outputs.send_email.data.result" → [Action Icon] Send Email • data.result
 * - "loop.item.name" → [Loop Icon] Current Item • item.name
 */
const VariablePill = ({
  value,
  onEdit,
  onRemove,
  nodeMetadata = {},
  compact = false,
  editable = true
}) => {
  // Parse variable path to get category and friendly info
  const parseVariablePath = (path) => {
    if (!path) return null;

    // Remove {{ }} if present
    const cleanPath = path.replace(/^{{|}}/g, '').trim();

    // Split the path
    const parts = cleanPath.split('.');
    if (parts.length === 0) return null;

    const category = parts[0];

    // Get icon and label based on category
    let icon, categoryLabel, color;

    switch (category) {
      case 'input':
        icon = <CursorArrowRaysIcon className="w-4 h-4" />;
        categoryLabel = 'Trigger Input';
        color = 'blue';
        break;
      case 'node_outputs':
        icon = <CodeBracketIcon className="w-4 h-4" />;
        // Get node label from metadata if available
        const nodeId = parts[1];
        const nodeInfo = nodeMetadata[nodeId] || {};
        categoryLabel = nodeInfo.label || nodeId || 'Previous Step';
        color = 'indigo';
        break;
      case 'flow':
        icon = <CalculatorIcon className="w-4 h-4" />;
        categoryLabel = 'Flow Information';
        color = 'purple';
        break;
      case 'loop':
        icon = <ArrowPathIcon className="w-4 h-4" />;
        categoryLabel = 'Current Item';
        color = 'green';
        break;
      case 'global':
        icon = <GlobeAltIcon className="w-4 h-4" />;
        categoryLabel = 'Global Variables';
        color = 'gray';
        break;
      case 'data':
        icon = <DocumentTextIcon className="w-4 h-4" />;
        categoryLabel = 'Data';
        color = 'teal';
        break;
      default:
        icon = <DocumentTextIcon className="w-4 h-4" />;
        categoryLabel = category;
        color = 'gray';
    }

    // Get field path (everything after category, or after node_id for node_outputs)
    let fieldPath;
    if (category === 'node_outputs' && parts.length > 2) {
      fieldPath = parts.slice(2).join('.');
    } else if (parts.length > 1) {
      fieldPath = parts.slice(1).join('.');
    } else {
      fieldPath = null;
    }

    return {
      icon,
      categoryLabel,
      fieldPath,
      color,
      rawPath: cleanPath
    };
  };

  const parsed = parseVariablePath(value);

  if (!parsed) {
    // Fallback for invalid/empty values
    return (
      <div className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 rounded text-sm">
        <DocumentTextIcon className="w-4 h-4" />
        <span className="text-xs">No variable selected</span>
        {editable && onRemove && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="ml-1 hover:bg-gray-200 rounded p-0.5"
            title="Remove"
          >
            <XMarkIcon className="w-3 h-3" />
          </button>
        )}
      </div>
    );
  }

  // Color classes based on category
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
  };

  const colorClass = colorClasses[parsed.color] || colorClasses.gray;

  if (compact) {
    // Compact version - just show the path
    return (
      <div className={`inline-flex items-center gap-1 px-2 py-0.5 border rounded ${colorClass} text-xs`}>
        {parsed.icon}
        <span className="font-medium truncate max-w-xs" title={parsed.rawPath}>
          {parsed.fieldPath || parsed.categoryLabel}
        </span>
        {editable && onRemove && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="hover:opacity-70"
            title="Remove"
          >
            <XMarkIcon className="w-3 h-3" />
          </button>
        )}
      </div>
    );
  }

  // Full version - show category • field
  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 border rounded-md ${colorClass} text-sm group relative`}
      title={parsed.rawPath}
    >
      <div className="flex items-center gap-1.5">
        {parsed.icon}
        <span className="font-semibold">{parsed.categoryLabel}</span>
        {parsed.fieldPath && (
          <>
            <span className="text-gray-400">•</span>
            <span className="font-normal">{parsed.fieldPath}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-0.5 ml-1">
        {editable && onEdit && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
            className="opacity-0 group-hover:opacity-100 hover:bg-black/5 rounded p-0.5 transition-opacity"
            title="Edit variable"
          >
            <PencilIcon className="w-3.5 h-3.5" />
          </button>
        )}
        {editable && onRemove && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="opacity-0 group-hover:opacity-100 hover:bg-black/5 rounded p-0.5 transition-opacity"
            title="Remove variable"
          >
            <XMarkIcon className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
};

export default VariablePill;
