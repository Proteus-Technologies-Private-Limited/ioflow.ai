import React, { useState } from 'react';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  PencilSquareIcon,
  Bars3Icon,
} from '@heroicons/react/24/outline';
import { getBlockType } from '../blockTypes';

// Config component imports
import HeroBlockConfig from './configs/HeroBlockConfig';
import TextBlockConfig from './configs/TextBlockConfig';
import ImageBlockConfig from './configs/ImageBlockConfig';
import ImageGalleryBlockConfig from './configs/ImageGalleryBlockConfig';
import TriggerFormConfig from './configs/TriggerFormConfig';
import ExecutionDisplayConfig from './configs/ExecutionDisplayConfig';
import ResultDisplayConfig from './configs/ResultDisplayConfig';
import DocumentationBlockConfig from './configs/DocumentationBlockConfig';
import FeaturesBlockConfig from './configs/FeaturesBlockConfig';
import ColumnsBlockConfig from './configs/ColumnsBlockConfig';
import SpacerBlockConfig from './configs/SpacerBlockConfig';
import DividerBlockConfig from './configs/DividerBlockConfig';
import CTAButtonBlockConfig from './configs/CTAButtonBlockConfig';
import PricingBlockConfig from './configs/PricingBlockConfig';
import ExecutionsListConfig from './configs/ExecutionsListConfig';
import TaskInboxConfig from './configs/TaskInboxConfig';

const CONFIG_COMPONENTS = {
  hero: HeroBlockConfig,
  text: TextBlockConfig,
  image: ImageBlockConfig,
  image_gallery: ImageGalleryBlockConfig,
  trigger_form: TriggerFormConfig,
  execution_display: ExecutionDisplayConfig,
  result_display: ResultDisplayConfig,
  documentation: DocumentationBlockConfig,
  features: FeaturesBlockConfig,
  columns: ColumnsBlockConfig,
  spacer: SpacerBlockConfig,
  divider: DividerBlockConfig,
  cta_button: CTAButtonBlockConfig,
  executions_list: ExecutionsListConfig,
  task_inbox: TaskInboxConfig,
  pricing: PricingBlockConfig,
};

export default function BlockWrapper({
  section,
  index,
  total,
  onUpdate,
  onDelete,
  onDuplicate,
  onMoveUp,
  onMoveDown,
  appId,
  manualVariables,
  // Drag props
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  isDragging,
}) {
  const [expanded, setExpanded] = useState(false);
  const blockType = getBlockType(section.type);
  const ConfigComponent = CONFIG_COMPONENTS[section.type];
  const IconComponent = blockType?.icon;

  const handleConfigChange = (newConfig) => {
    onUpdate({ ...section, config: newConfig });
  };

  return (
    <div
      className={`border rounded-lg bg-white transition-all ${
        isDragging ? 'opacity-50 border-primary' : 'border-gray-200 hover:border-gray-300'
      }`}
      draggable
      onDragStart={(e) => onDragStart(e, index)}
      onDragOver={(e) => onDragOver(e, index)}
      onDrop={(e) => onDrop(e, index)}
      onDragEnd={onDragEnd}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-600">
          <Bars3Icon className="w-4 h-4" />
        </div>

        {IconComponent && (
          <IconComponent className="w-4 h-4 text-gray-500" />
        )}

        <span className="text-sm font-medium text-gray-700 flex-1 truncate">
          {blockType?.name || section.type}
        </span>

        <span className="text-xs text-gray-400 mr-2">#{index + 1}</span>

        <div className="flex items-center gap-1">
          <button
            onClick={() => onMoveUp(index)}
            disabled={index === 0}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
            title="Move up"
          >
            <ChevronUpIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onMoveDown(index)}
            disabled={index === total - 1}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
            title="Move down"
          >
            <ChevronDownIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 text-gray-400 hover:text-primary"
            title="Edit"
          >
            <PencilSquareIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDuplicate(index)}
            className="p-1 text-gray-400 hover:text-blue-500"
            title="Duplicate"
          >
            <DocumentDuplicateIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(index)}
            className="p-1 text-gray-400 hover:text-red-500"
            title="Delete"
          >
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Config Panel */}
      {expanded && ConfigComponent && (
        <div className="border-t border-gray-100 px-4 py-4 bg-gray-50/50">
          <ConfigComponent
            config={section.config}
            onChange={handleConfigChange}
            appId={appId}
            manualVariables={manualVariables}
          />
        </div>
      )}
    </div>
  );
}
