import React, { useState } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  PencilSquareIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import BLOCK_TYPES, { getBlockType, getDefaultConfig } from '../../blockTypes';

// Inline config components for nested blocks
import TextBlockConfig from './TextBlockConfig';
import ImageBlockConfig from './ImageBlockConfig';
import FeaturesBlockConfig from './FeaturesBlockConfig';
import SpacerBlockConfig from './SpacerBlockConfig';
import DividerBlockConfig from './DividerBlockConfig';
import CTAButtonBlockConfig from './CTAButtonBlockConfig';
import PricingBlockConfig from './PricingBlockConfig';

const NESTED_CONFIG_MAP = {
  text: TextBlockConfig,
  image: ImageBlockConfig,
  features: FeaturesBlockConfig,
  spacer: SpacerBlockConfig,
  divider: DividerBlockConfig,
  cta_button: CTAButtonBlockConfig,
  pricing: PricingBlockConfig,
};

// Block types allowed inside columns
const ALLOWED_NESTED_TYPES = ['text', 'image', 'features', 'spacer', 'divider', 'cta_button', 'pricing'];

export default function ColumnsBlockConfig({ config, onChange, appId }) {
  const [expandedBlock, setExpandedBlock] = useState(null);
  const [addMenuOpen, setAddMenuOpen] = useState(null);

  const columns = config.columns || 2;
  const children = config.children || [];

  const ensureChildren = (colCount) => {
    const newChildren = [...children];
    while (newChildren.length < colCount) {
      newChildren.push({ sections: [] });
    }
    return newChildren.slice(0, colCount);
  };

  const handleColumnsChange = (newCount) => {
    const newChildren = ensureChildren(newCount);
    onChange({ ...config, columns: newCount, children: newChildren });
  };

  const addBlockToColumn = (colIdx, blockType) => {
    const newChildren = ensureChildren(columns);
    const newSection = {
      id: crypto.randomUUID(),
      type: blockType,
      config: getDefaultConfig(blockType),
    };
    newChildren[colIdx] = {
      ...newChildren[colIdx],
      sections: [...(newChildren[colIdx].sections || []), newSection],
    };
    onChange({ ...config, children: newChildren });
    setAddMenuOpen(null);
    setExpandedBlock(`${colIdx}-${newChildren[colIdx].sections.length - 1}`);
  };

  const removeBlockFromColumn = (colIdx, secIdx) => {
    const newChildren = ensureChildren(columns);
    newChildren[colIdx] = {
      ...newChildren[colIdx],
      sections: newChildren[colIdx].sections.filter((_, i) => i !== secIdx),
    };
    onChange({ ...config, children: newChildren });
    if (expandedBlock === `${colIdx}-${secIdx}`) setExpandedBlock(null);
  };

  const updateBlockInColumn = (colIdx, secIdx, updatedSection) => {
    const newChildren = ensureChildren(columns);
    const newSections = [...newChildren[colIdx].sections];
    newSections[secIdx] = updatedSection;
    newChildren[colIdx] = { ...newChildren[colIdx], sections: newSections };
    onChange({ ...config, children: newChildren });
  };

  const moveBlock = (colIdx, secIdx, direction) => {
    const newChildren = ensureChildren(columns);
    const sections = [...newChildren[colIdx].sections];
    const targetIdx = secIdx + direction;
    if (targetIdx < 0 || targetIdx >= sections.length) return;
    [sections[secIdx], sections[targetIdx]] = [sections[targetIdx], sections[secIdx]];
    newChildren[colIdx] = { ...newChildren[colIdx], sections };
    onChange({ ...config, children: newChildren });
  };

  return (
    <div className="space-y-4">
      {/* Column count & gap */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">Columns</label>
          <select
            value={columns}
            onChange={(e) => handleColumnsChange(parseInt(e.target.value))}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          >
            <option value={2}>2 Columns</option>
            <option value={3}>3 Columns</option>
            <option value={4}>4 Columns</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">Gap</label>
          <select
            value={config.gap || 'lg'}
            onChange={(e) => onChange({ ...config, gap: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          >
            <option value="sm">Small</option>
            <option value="md">Medium</option>
            <option value="lg">Large</option>
            <option value="xl">Extra Large</option>
          </select>
        </div>
      </div>

      {/* Column content editors */}
      <div className="space-y-3">
        {ensureChildren(columns).map((col, colIdx) => (
          <div key={colIdx} className="border border-gray-200 rounded-lg overflow-visible">
            {/* Column header */}
            <div className="bg-gray-100 px-3 py-2 flex items-center justify-between rounded-t-lg">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                Column {colIdx + 1}
              </span>
              <span className="text-xs text-gray-400">
                {(col.sections || []).length} block{(col.sections || []).length !== 1 ? 's' : ''}
              </span>
            </div>

            {/* Blocks in this column */}
            <div className="p-2 space-y-1.5">
              {(col.sections || []).map((section, secIdx) => {
                const blockType = getBlockType(section.type);
                const Icon = blockType?.icon;
                const isExpanded = expandedBlock === `${colIdx}-${secIdx}`;
                const ConfigComponent = NESTED_CONFIG_MAP[section.type];

                return (
                  <div key={section.id} className="border border-gray-200 rounded bg-white">
                    <div className="flex items-center gap-1.5 px-2 py-1.5">
                      {Icon && <Icon className="w-3.5 h-3.5 text-gray-400" />}
                      <span className="text-xs font-medium text-gray-700 flex-1 truncate">
                        {blockType?.name || section.type}
                      </span>
                      <button
                        onClick={() => moveBlock(colIdx, secIdx, -1)}
                        disabled={secIdx === 0}
                        className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                      >
                        <ChevronUpIcon className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => moveBlock(colIdx, secIdx, 1)}
                        disabled={secIdx === (col.sections || []).length - 1}
                        className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                      >
                        <ChevronDownIcon className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => setExpandedBlock(isExpanded ? null : `${colIdx}-${secIdx}`)}
                        className="p-0.5 text-gray-400 hover:text-primary"
                      >
                        <PencilSquareIcon className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => removeBlockFromColumn(colIdx, secIdx)}
                        className="p-0.5 text-gray-400 hover:text-red-500"
                      >
                        <TrashIcon className="w-3 h-3" />
                      </button>
                    </div>

                    {isExpanded && ConfigComponent && (
                      <div className="border-t border-gray-100 px-3 py-3 bg-gray-50/50">
                        <ConfigComponent
                          config={section.config}
                          onChange={(newConfig) =>
                            updateBlockInColumn(colIdx, secIdx, { ...section, config: newConfig })
                          }
                          appId={appId}
                        />
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Add block - inline list, not a dropdown */}
              {addMenuOpen === colIdx ? (
                <div className="border border-primary/30 rounded-lg bg-primary/5 p-2">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-primary">Choose block type</span>
                    <button
                      onClick={() => setAddMenuOpen(null)}
                      className="p-0.5 text-gray-400 hover:text-gray-600"
                    >
                      <XMarkIcon className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1">
                    {ALLOWED_NESTED_TYPES.map((type) => {
                      const bt = getBlockType(type);
                      if (!bt) return null;
                      const BtIcon = bt.icon;
                      return (
                        <button
                          key={type}
                          onClick={() => addBlockToColumn(colIdx, type)}
                          className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-white border border-gray-200 hover:border-primary hover:bg-primary/5 text-left transition-colors"
                        >
                          <BtIcon className="w-3.5 h-3.5 text-gray-500" />
                          <span className="text-xs text-gray-700">{bt.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setAddMenuOpen(colIdx)}
                  className="w-full flex items-center justify-center gap-1 px-2 py-2 border-2 border-dashed border-gray-300 rounded text-xs text-gray-500 hover:border-primary hover:text-primary transition-colors"
                >
                  <PlusIcon className="w-3.5 h-3.5" />
                  Add Block
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
