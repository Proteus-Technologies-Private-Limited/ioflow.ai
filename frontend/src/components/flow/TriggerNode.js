import React from 'react';
import { Handle, Position } from 'reactflow';
import { BoltIcon, ClockIcon, CursorArrowRaysIcon, GlobeAltIcon, CodeBracketIcon, FolderIcon, ChatBubbleLeftRightIcon } from '@heroicons/react/24/outline';
import { getIconForTriggerType } from '../../plugins/IconRegistry';
import { withResize } from './ResizableNode';
import ValidationErrorTooltip from './ValidationErrorTooltip';
import OverlapIndicator from './OverlapIndicator';

const TriggerNodeBase = ({ id, data, isConnectable }) => {
  // Check for validation errors
  const hasErrors = data?.validationErrors && data.validationErrors.length > 0;
  const hasWarnings = data?.validationErrors && data.validationErrors.some(e => e.type === 'warning');
  const hasCriticalErrors = data?.validationErrors && data.validationErrors.some(e => e.type === 'error');
  
  const getIcon = () => {
    const IconComponent = getIconForTriggerType(data.triggerType);
    return <IconComponent className="w-5 h-5" />;
  };

  const getTypeLabel = () => {
    switch (data.triggerType) {
      case 'application_event':
      case 'event':
        return 'Event';
      case 'webhook':
        return 'Webhook';
      case 'schedule':
        return 'Schedule';
      case 'file_change':
        return 'File Change';
      case 'mqtt':
        return 'MQTT';
      case 'api_call':
        return 'API Call';
      case 'chat_input':
        return 'Chat';
      default:
        return 'Manual';
    }
  };

  const isManual = !data.triggerType || data.triggerType === 'manual';
  const bgColor = isManual ? 'bg-orange-50' : 'bg-green-50';
  const borderColor = isManual ? 'border-orange-300' : 'border-green-300';
  const textColor = isManual ? 'text-orange-600' : 'text-green-600';

  return (
    <div className={`${bgColor} border-2 ${hasCriticalErrors ? 'border-red-400' : hasWarnings ? 'border-yellow-400' : borderColor} rounded-lg p-4 w-full h-full overflow-hidden relative`}>
      <div className="flex items-center justify-between mb-2">
        <div className={textColor}>{getIcon()}</div>
        <span className={`text-xs ${textColor} font-medium`}>{getTypeLabel()}</span>
      </div>
      <div className="font-medium text-gray-800">{data.label}</div>
      {(data.eventDisplayName || data.eventName) && (
        <div className="text-xs text-gray-500 mt-1">{data.eventDisplayName || data.eventName}</div>
      )}
      {data.triggerType === 'file_change' && data.folderPath && (
        <div className="text-xs text-gray-500 mt-1">
          {data.folderPath} ({data.filePattern || '*'})
        </div>
      )}
      {(data.triggerType === 'mqtt' || data.eventTriggerKind === 'mqtt') && data.mqttTopicFilter && (
        <div className="text-xs text-gray-500 mt-1">
          Topic: {data.mqttTopicFilter}
        </div>
      )}
      {/* Display manual variables for manual trigger (hidden in execution mode) */}
      {!data.executionMode && data.triggerType === 'manual' && data.manualVariables?.length > 0 && (
        <div className="mt-2 space-y-1">
          <div className="text-xs text-gray-500 font-medium">Variables:</div>
          {data.manualVariables.slice(0, 3).map((v, idx) => (
            <div key={idx} className="text-xs text-blue-600 font-mono bg-blue-50 px-1 rounded truncate">
              input.{v.name}
            </div>
          ))}
          {data.manualVariables.length > 3 && (
            <div className="text-xs text-gray-400">+{data.manualVariables.length - 3} more</div>
          )}
        </div>
      )}
      {/* Display chat input variables (hidden in execution mode) */}
      {!data.executionMode && data.triggerType === 'chat_input' && (
        <div className="mt-2 space-y-1">
          <div className="text-xs text-gray-500 font-medium">Variables:</div>
          <div className="text-xs text-blue-600 font-mono bg-blue-50 px-1 rounded">input.message</div>
          <div className="text-xs text-blue-600 font-mono bg-blue-50 px-1 rounded">input.session_id</div>
          <div className="text-xs text-gray-400 font-mono bg-gray-50 px-1 rounded">input.is_first_message</div>
        </div>
      )}
      <div className="absolute bottom-1 right-2 text-[10px] text-gray-400">{id}</div>
      
      {/* Validation error tooltip */}
      {hasErrors && (
        <ValidationErrorTooltip 
          errors={data.validationErrors}
          className="absolute top-1 right-1"
          onRevalidate={data.onRevalidate}
        />
      )}
      
      {/* Overlap indicator */}
      {data?.showOverlapIndicator && (
        <OverlapIndicator
          overlappingCount={data.overlappingNodes?.length || 0}
          type="node"
          position="bottom-left"
          showWarning={data.overlappingNodes?.length > 2}
        />
      )}
      
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        isConnectable={isConnectable}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        isConnectable={isConnectable}
      />
    </div>
  );
};

const TriggerNode = withResize(TriggerNodeBase);

export default TriggerNode;