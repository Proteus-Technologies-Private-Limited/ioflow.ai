import React, { useState, useRef, useEffect } from 'react';
import {
  PlusIcon,
  EyeIcon,
  EyeSlashIcon,
  SwatchIcon,
  ArrowPathIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';
import BLOCK_TYPES, { BLOCK_CATEGORIES } from '../blockTypes';

/**
 * DesignerToolbar - Top toolbar with Add Block, Preview toggle, Theme, Save, Reset
 */
export default function DesignerToolbar({
  onAddBlock,
  showPreview,
  onTogglePreview,
  onThemeClick,
  onSave,
  onReset,
  saving,
  hasChanges,
  hasHITLNode = false,
}) {
  const [showAddMenu, setShowAddMenu] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowAddMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleAddBlock = (type) => {
    onAddBlock(type);
    setShowAddMenu(false);
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Add Block */}
      <div className="relative" ref={menuRef}>
        <button
          onClick={() => setShowAddMenu(!showAddMenu)}
          className="flex items-center gap-1.5 px-3 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition"
        >
          <PlusIcon className="w-4 h-4" />
          Add Block
        </button>

        {showAddMenu && (
          <div className="absolute top-full left-0 mt-1 w-72 bg-white rounded-xl shadow-xl border border-gray-200 z-50 max-h-[400px] overflow-y-auto">
            {BLOCK_CATEGORIES.map((category) => (
              <div key={category}>
                <div className="px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider bg-gray-50">
                  {category}
                </div>
                {BLOCK_TYPES.filter((b) => b.category === category).map((block) => {
                  const Icon = block.icon;
                  const disabled = block.requiresHITL && !hasHITLNode;
                  return (
                    <button
                      key={block.type}
                      onClick={() => !disabled && handleAddBlock(block.type)}
                      disabled={disabled}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition ${
                        disabled ? 'opacity-40 cursor-not-allowed bg-gray-50' : 'hover:bg-gray-50'
                      }`}
                      title={disabled ? 'Requires a Human-in-the-Loop node in the flow' : ''}
                    >
                      <Icon className="w-5 h-5 text-gray-500 shrink-0" />
                      <div>
                        <div className="text-sm font-medium text-gray-700">
                          {block.name}
                          {disabled && <span className="ml-1 text-[10px] text-red-400">(No Human Review node)</span>}
                        </div>
                        <div className="text-xs text-gray-400">{block.description}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Preview Toggle */}
      <button
        onClick={onTogglePreview}
        className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border transition ${
          showPreview
            ? 'bg-primary/10 text-primary border-primary/30'
            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
        }`}
      >
        {showPreview ? (
          <EyeIcon className="w-4 h-4" />
        ) : (
          <EyeSlashIcon className="w-4 h-4" />
        )}
        {showPreview ? 'Preview' : 'Preview'}
      </button>

      {/* Theme */}
      <button
        onClick={onThemeClick}
        className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 transition"
      >
        <SwatchIcon className="w-4 h-4" />
        Theme
      </button>

      <div className="flex-1" />

      {/* Reset */}
      <button
        onClick={onReset}
        className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 transition"
      >
        <ArrowPathIcon className="w-4 h-4" />
        Reset
      </button>

      {/* Save */}
      <button
        onClick={onSave}
        disabled={saving || !hasChanges}
        className="flex items-center gap-1.5 px-4 py-2 bg-gradient-primary text-white text-sm font-medium rounded-lg hover:shadow-lg transition disabled:opacity-50"
      >
        {saving ? (
          <ArrowPathIcon className="w-4 h-4 animate-spin" />
        ) : (
          <CheckIcon className="w-4 h-4" />
        )}
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  );
}
