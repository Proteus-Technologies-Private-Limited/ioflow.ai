import React, { useState, useEffect, useRef } from 'react';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';
import IsolatedField from '../flow/IsolatedParameterInput';

/**
 * PrerequisiteCard - A card component for displaying and executing prerequisite flows
 * with inline expansion capability.
 *
 * Props:
 * - prerequisite: The prerequisite flow data
 * - status: 'not_run' | 'running' | 'completed' | 'failed' | 'skipped'
 * - onRun: Callback to execute the prerequisite flow
 * - onSkip: Callback to skip optional prerequisite
 * - outputs: Output data from the prerequisite execution (for passing to main flow)
 * - initialInputs: Pre-filled input values (from previous executions)
 */
const PrerequisiteCard = ({
  prerequisite,
  status = 'not_run',
  onRun,
  onSkip,
  outputs = null,
  initialInputs = {}
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [formData, setFormData] = useState(initialInputs);
  const [executing, setExecuting] = useState(false);
  const [executionLogs, setExecutionLogs] = useState([]);
  const contentRef = useRef(null);

  // Update form data when initial inputs change
  useEffect(() => {
    setFormData(initialInputs);
  }, [initialInputs]);

  const handleInputChange = (name, value) => {
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleExecute = async () => {
    setExecuting(true);
    setExecutionLogs([]);

    try {
      // Call the parent's onRun with form data
      const result = await onRun(prerequisite, formData);

      if (result.success) {
        setExecutionLogs([{ type: 'success', message: 'Execution completed successfully' }]);
      } else {
        setExecutionLogs([{ type: 'error', message: result.error || 'Execution failed' }]);
      }
    } catch (error) {
      setExecutionLogs([{ type: 'error', message: error.message || 'Execution failed' }]);
    } finally {
      setExecuting(false);
    }
  };

  const handleSkip = () => {
    if (onSkip) {
      onSkip(prerequisite);
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
      case 'skipped':
        return <XCircleIcon className="w-5 h-5 text-gray-400" />;
      default:
        return <div className="w-5 h-5 rounded-full border-2 border-gray-300" />;
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
      case 'skipped':
        return 'Skipped';
      default:
        return 'Not run';
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
      case 'skipped':
        return 'bg-gray-50 border-gray-200 dark:bg-gray-800/50 dark:border-gray-700';
      default:
        return 'bg-white border-gray-200 dark:bg-gray-800 dark:border-gray-700';
    }
  };

  const inputParameters = prerequisite.input_parameters || [];

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
                  {prerequisite.display_name || prerequisite.app_name}
                </h4>
                {prerequisite.is_mandatory && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                    Required
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {prerequisite.app_description || 'No description'}
              </p>
              {prerequisite.documentation && (
                <div className="flex items-start mt-1 text-xs text-blue-600 dark:text-blue-400">
                  <InformationCircleIcon className="w-3.5 h-3.5 mr-1 flex-shrink-0 mt-0.5" />
                  <span>{prerequisite.documentation}</span>
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
          isExpanded ? 'max-h-[800px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 dark:border-gray-700">
          {/* Input Parameters */}
          {inputParameters.length > 0 && (
            <div className="mb-4">
              <h5 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Input Parameters
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

          {/* Output preview (if completed) */}
          {status === 'completed' && outputs && (
            <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <h5 className="text-xs font-medium text-green-700 dark:text-green-300 mb-2">
                Outputs (available for main flow)
              </h5>
              <pre className="text-xs text-green-600 dark:text-green-400 overflow-x-auto">
                {JSON.stringify(outputs, null, 2)}
              </pre>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center space-x-3">
            <button
              onClick={handleExecute}
              disabled={executing || status === 'running'}
              className={`
                inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg
                ${status === 'completed'
                  ? 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-300'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
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
                  Run Now
                </>
              )}
            </button>

            {!prerequisite.is_mandatory && status !== 'completed' && status !== 'skipped' && (
              <button
                onClick={handleSkip}
                disabled={executing}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
              >
                Skip
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PrerequisiteCard;
