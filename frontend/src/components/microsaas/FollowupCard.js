import React, { useState, useEffect, useRef } from 'react';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  PencilIcon,
  LinkIcon,
  ArrowRightIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';
import IsolatedField from '../flow/IsolatedParameterInput';

/**
 * FollowupCard - A card component for displaying and executing follow-up flows
 * with auto-mapped values preview and inline expansion.
 *
 * Props:
 * - followup: The follow-up flow data
 * - status: 'available' | 'running' | 'completed' | 'failed'
 * - autoMappedValues: Object with auto-mapped parameter values from main flow output
 * - onRun: Callback to execute the follow-up flow
 * - mainFlowOutputs: Outputs from the main flow (for auto-mapping)
 */
const FollowupCard = ({
  followup,
  status = 'available',
  autoMappedValues = {},
  onRun,
  mainFlowOutputs = {}
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [formData, setFormData] = useState({});
  const [isCustomizing, setIsCustomizing] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionLogs, setExecutionLogs] = useState([]);
  const [executionResult, setExecutionResult] = useState(null);
  const contentRef = useRef(null);

  // Initialize form data with auto-mapped values
  useEffect(() => {
    const initialData = { ...autoMappedValues };
    // Fill in with defaults for any unmapped required fields
    (followup.input_parameters || []).forEach(param => {
      if (initialData[param.name] === undefined && param.default_value !== undefined) {
        initialData[param.name] = param.default_value;
      }
    });
    setFormData(initialData);
  }, [autoMappedValues, followup.input_parameters]);

  const handleInputChange = (name, value) => {
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleRunWithCurrentData = async () => {
    await executeFollowup(formData);
  };

  const handleRunWithCustomInputs = async () => {
    await executeFollowup(formData);
    setIsCustomizing(false);
  };

  const executeFollowup = async (data) => {
    setExecuting(true);
    setExecutionLogs([]);
    setExecutionResult(null);

    try {
      const result = await onRun(followup, data);

      if (result.success) {
        setExecutionLogs([{ type: 'success', message: 'Execution completed successfully' }]);
        setExecutionResult(result.data);
      } else {
        setExecutionLogs([{ type: 'error', message: result.error || 'Execution failed' }]);
      }
    } catch (error) {
      setExecutionLogs([{ type: 'error', message: error.message || 'Execution failed' }]);
    } finally {
      setExecuting(false);
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircleIcon className="w-5 h-5 text-red-500" />;
      case 'running':
        return <ArrowPathIcon className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <ArrowRightIcon className="w-5 h-5 text-green-500" />;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'running':
        return 'Running...';
      default:
        return 'Available';
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800';
      case 'failed':
        return 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800';
      case 'running':
        return 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800';
      default:
        return 'bg-white border-gray-200 dark:bg-gray-800 dark:border-gray-700';
    }
  };

  const inputParameters = followup.input_parameters || [];
  const autoMappedParams = Object.keys(autoMappedValues);

  return (
    <div className={`rounded-lg border transition-all duration-300 ${getStatusColor()}`}>
      {/* Header - Always visible */}
      <div
        className="p-4 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-3">
            {/* Status icon */}
            <div className="flex-shrink-0 mt-0.5">
              {getStatusIcon()}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2">
                <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                  {followup.display_name || followup.app_name}
                </h4>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {followup.app_description || 'No description'}
              </p>

              {/* Auto-mapped parameters preview */}
              {autoMappedParams.length > 0 && (
                <div className="flex items-center mt-1.5 text-xs text-green-600 dark:text-green-400">
                  <LinkIcon className="w-3.5 h-3.5 mr-1" />
                  <span>
                    Auto-filled: {autoMappedParams.slice(0, 3).join(', ')}
                    {autoMappedParams.length > 3 && ` +${autoMappedParams.length - 3} more`}
                  </span>
                </div>
              )}

              {followup.documentation && (
                <div className="flex items-start mt-1 text-xs text-blue-600 dark:text-blue-400">
                  <InformationCircleIcon className="w-3.5 h-3.5 mr-1 flex-shrink-0 mt-0.5" />
                  <span>{followup.documentation}</span>
                </div>
              )}
            </div>
          </div>

          {/* Right side - status and expand */}
          <div className="flex items-center space-x-3 ml-4">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {getStatusText()}
            </span>
            {isExpanded ? (
              <ChevronUpIcon className="w-5 h-5 text-gray-400" />
            ) : (
              <ChevronDownIcon className="w-5 h-5 text-gray-400" />
            )}
          </div>
        </div>
      </div>

      {/* Expanded content - Inline execution UI */}
      <div
        ref={contentRef}
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isExpanded ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 dark:border-gray-700">
          {/* Auto-mapped values summary */}
          {autoMappedParams.length > 0 && !isCustomizing && (
            <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <h5 className="text-xs font-medium text-green-700 dark:text-green-300 mb-2">
                Values from Main Flow Output
              </h5>
              <div className="space-y-1">
                {autoMappedParams.map((paramName) => (
                  <div key={paramName} className="flex items-start text-xs">
                    <span className="text-green-600 dark:text-green-400 font-medium min-w-[100px]">
                      {paramName}:
                    </span>
                    <span className="text-green-700 dark:text-green-300 ml-2 break-all">
                      {typeof autoMappedValues[paramName] === 'object'
                        ? JSON.stringify(autoMappedValues[paramName])
                        : String(autoMappedValues[paramName])}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Input Parameters (when customizing) */}
          {isCustomizing && inputParameters.length > 0 && (
            <div className="mb-4">
              <h5 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Customize Input Parameters
              </h5>
              <div className="space-y-3">
                {inputParameters.map((param) => (
                  <div key={param.name}>
                    <IsolatedField
                      variable={{
                        id: param.name,
                        name: param.name,
                        displayName: param.description || param.name,
                        dataType: param.type || 'string',
                        required: param.required
                      }}
                      value={formData[param.name] || ''}
                      onChange={(value) => handleInputChange(param.name, value)}
                    />
                    {autoMappedValues[param.name] !== undefined && (
                      <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                        Auto-mapped from main flow output
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Execution Logs */}
          {executionLogs.length > 0 && (
            <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
              <h5 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Execution Status
              </h5>
              <div className="space-y-1">
                {executionLogs.map((log, index) => (
                  <div
                    key={index}
                    className={`text-xs ${
                      log.type === 'error'
                        ? 'text-red-600 dark:text-red-400'
                        : log.type === 'success'
                        ? 'text-green-600 dark:text-green-400'
                        : 'text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    {log.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Result preview (if completed) */}
          {status === 'completed' && executionResult && (
            <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <h5 className="text-xs font-medium text-green-700 dark:text-green-300 mb-2">
                Result
              </h5>
              <pre className="text-xs text-green-600 dark:text-green-400 overflow-x-auto max-h-40">
                {typeof executionResult === 'object'
                  ? JSON.stringify(executionResult, null, 2)
                  : String(executionResult)}
              </pre>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center space-x-3">
            {!isCustomizing ? (
              <>
                <button
                  onClick={handleRunWithCurrentData}
                  disabled={executing || status === 'running'}
                  className={`
                    inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg
                    ${status === 'completed'
                      ? 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-300'
                      : 'bg-green-600 text-white hover:bg-green-700'
                    }
                    disabled:opacity-50 disabled:cursor-not-allowed
                    transition-colors
                  `}
                >
                  {executing || status === 'running' ? (
                    <>
                      <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                      Running...
                    </>
                  ) : status === 'completed' ? (
                    <>
                      <ArrowPathIcon className="w-4 h-4 mr-2" />
                      Run Again
                    </>
                  ) : (
                    <>
                      <PlayIcon className="w-4 h-4 mr-2" />
                      Run with Current Data
                    </>
                  )}
                </button>

                {inputParameters.length > 0 && (
                  <button
                    onClick={() => setIsCustomizing(true)}
                    disabled={executing}
                    className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    <PencilIcon className="w-4 h-4 mr-2" />
                    Customize Inputs
                  </button>
                )}
              </>
            ) : (
              <>
                <button
                  onClick={handleRunWithCustomInputs}
                  disabled={executing}
                  className="inline-flex items-center px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {executing ? (
                    <>
                      <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                      Running...
                    </>
                  ) : (
                    <>
                      <PlayIcon className="w-4 h-4 mr-2" />
                      Run with Custom Values
                    </>
                  )}
                </button>

                <button
                  onClick={() => {
                    setIsCustomizing(false);
                    setFormData({ ...autoMappedValues });
                  }}
                  disabled={executing}
                  className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FollowupCard;
