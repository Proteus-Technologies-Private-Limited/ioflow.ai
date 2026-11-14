import React from 'react';
import {
  CursorArrowRaysIcon,
  CodeBracketIcon,
  CalculatorIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  GlobeAltIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

/**
 * InlineVariablePills Component
 * Displays text with inline variable pills
 * Parses text like "Hello {{input.name}}, order {{loop.item.id}}"
 * and renders variables as pills
 */
const InlineVariablePills = ({
  value,
  nodeMetadata = {},
  onEdit,
  readOnly = false,
}) => {
  // Parse value to extract text and variables
  const parseValue = (text) => {
    if (!text) return [];

    const parts = [];
    const regex = /{{([^}]+)}}/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      // Add text before the variable
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: text.substring(lastIndex, match.index)
        });
      }

      // Add the variable
      parts.push({
        type: 'variable',
        content: match[1].trim(),
        raw: match[0]
      });

      lastIndex = regex.lastIndex;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push({
        type: 'text',
        content: text.substring(lastIndex)
      });
    }

    return parts;
  };

  // Get friendly display for a variable path
  const getVariableDisplay = (variablePath) => {
    const parts = variablePath.split('.');
    if (parts.length === 0) return { category: '', field: variablePath };

    const category = parts[0];
    let categoryLabel, icon, color;

    switch (category) {
      case 'input':
        icon = <CursorArrowRaysIcon className="w-3 h-3" />;
        categoryLabel = 'Trigger Input';
        color = 'blue';
        break;
      case 'node_outputs':
        icon = <CodeBracketIcon className="w-3 h-3" />;
        const nodeId = parts[1];
        const nodeInfo = nodeMetadata[nodeId] || {};
        categoryLabel = nodeInfo.label || nodeId || 'Previous Step';
        color = 'indigo';
        break;
      case 'flow':
        icon = <CalculatorIcon className="w-3 h-3" />;
        categoryLabel = 'Flow Info';
        color = 'purple';
        break;
      case 'loop':
        icon = <ArrowPathIcon className="w-3 h-3" />;
        categoryLabel = 'Current Item';
        color = 'green';
        break;
      case 'global':
        icon = <GlobeAltIcon className="w-3 h-3" />;
        categoryLabel = 'Global';
        color = 'gray';
        break;
      case 'data':
        icon = <DocumentTextIcon className="w-3 h-3" />;
        categoryLabel = 'Data';
        color = 'teal';
        break;
      default:
        icon = <DocumentTextIcon className="w-3 h-3" />;
        categoryLabel = category;
        color = 'gray';
    }

    // Get field path
    let fieldPath;
    if (category === 'node_outputs' && parts.length > 2) {
      fieldPath = parts.slice(2).join('.');
    } else if (parts.length > 1) {
      fieldPath = parts.slice(1).join('.');
    } else {
      fieldPath = '';
    }

    return {
      icon,
      categoryLabel,
      fieldPath,
      color,
      fullPath: variablePath
    };
  };

  // Color classes for pills
  const getColorClasses = (color) => {
    const colorMap = {
      blue: 'bg-blue-100 text-blue-800 border-blue-300',
      indigo: 'bg-indigo-100 text-indigo-800 border-indigo-300',
      purple: 'bg-purple-100 text-purple-800 border-purple-300',
      green: 'bg-green-100 text-green-800 border-green-300',
      gray: 'bg-gray-100 text-gray-800 border-gray-300',
      teal: 'bg-teal-100 text-teal-800 border-teal-300',
    };
    return colorMap[color] || colorMap.gray;
  };

  const parts = parseValue(value);

  if (parts.length === 0) {
    return <span className="text-gray-400 text-sm">No value</span>;
  }

  return (
    <div
      className="flex flex-wrap items-center gap-1 p-2 bg-gray-50 rounded border border-gray-200 min-h-[40px] cursor-text hover:bg-gray-100 transition-colors"
      onClick={!readOnly ? onEdit : undefined}
      title="Click to edit"
    >
      {parts.map((part, index) => {
        if (part.type === 'text') {
          return (
            <span key={`text-${index}`} className="text-sm text-gray-900">
              {part.content}
            </span>
          );
        } else {
          // Variable pill - each variable gets its own pill
          const display = getVariableDisplay(part.content);
          const colorClasses = getColorClasses(display.color);

          return (
            <span
              key={`var-${index}-${part.content}`}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium ${colorClasses} cursor-pointer hover:opacity-80 transition-opacity`}
              title={`Click to edit: ${part.content}`}
              onClick={(e) => {
                if (!readOnly && onEdit) {
                  e.stopPropagation();
                  onEdit();
                }
              }}
            >
              {display.icon}
              <span className="font-semibold">{display.categoryLabel}</span>
              {display.fieldPath && (
                <>
                  <span className="text-gray-500">•</span>
                  <span>{display.fieldPath}</span>
                </>
              )}
            </span>
          );
        }
      })}
    </div>
  );
};

export default InlineVariablePills;
