import React, { useState } from 'react';
import { XMarkIcon, PlayIcon, DocumentDuplicateIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import toast from 'react-hot-toast';
import MCPParameterForm from './MCPParameterForm';
import MCPResponseViewer from './MCPResponseViewer';

const MCPToolExecutor = ({ tool, onClose, onExecute }) => {
  const [parameters, setParameters] = useState({});
  const [executing, setExecuting] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [executionTime, setExecutionTime] = useState(null);

  const handleParameterChange = (paramName, value) => {
    setParameters(prev => ({
      ...prev,
      [paramName]: value
    }));
  };

  const validateParameters = () => {
    if (!tool.parameters || !tool.parameters.required) return true;
    
    for (const required of tool.parameters.required) {
      if (!parameters[required]) {
        toast.error(`Required parameter "${required}" is missing`);
        return false;
      }
    }
    return true;
  };

  const handleExecute = async () => {
    if (!validateParameters()) return;

    setExecuting(true);
    setError(null);
    setResponse(null);
    const startTime = Date.now();

    try {
      const result = await axios.post('/api/mcp/tools/execute', {
        tool: tool.name,
        parameters
      });

      const endTime = Date.now();
      const execTime = (endTime - startTime) / 1000;
      setExecutionTime(execTime);

      if (result.data.success) {
        setResponse(result.data.result);
        toast.success(`Tool executed successfully in ${execTime.toFixed(2)}s`);
        
        if (onExecute) {
          onExecute({
            success: true,
            result: result.data.result,
            execution_time: execTime
          });
        }
      } else {
        setError(result.data.error || 'Execution failed');
        toast.error(result.data.error || 'Tool execution failed');
        
        if (onExecute) {
          onExecute({
            success: false,
            error: result.data.error,
            execution_time: execTime
          });
        }
      }
    } catch (err) {
      const endTime = Date.now();
      const execTime = (endTime - startTime) / 1000;
      setExecutionTime(execTime);
      
      const errorMessage = err.response?.data?.detail || err.message;
      setError(errorMessage);
      toast.error(`Execution failed: ${errorMessage}`);
      
      if (onExecute) {
        onExecute({
          success: false,
          error: errorMessage,
          execution_time: execTime
        });
      }
    } finally {
      setExecuting(false);
    }
  };

  const handleCopyParameters = () => {
    const json = JSON.stringify(parameters, null, 2);
    navigator.clipboard.writeText(json);
    toast.success('Parameters copied to clipboard');
  };

  const handleCopyResponse = () => {
    const json = JSON.stringify(response, null, 2);
    navigator.clipboard.writeText(json);
    toast.success('Response copied to clipboard');
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b bg-gray-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                Test MCP Tool: {tool.name}
              </h2>
              <p className="mt-1 text-sm text-gray-500">{tool.description}</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Left Panel - Parameters */}
          <div className="w-1/2 border-r overflow-y-auto p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900">Parameters</h3>
                {Object.keys(parameters).length > 0 && (
                  <button
                    onClick={handleCopyParameters}
                    className="text-sm text-gray-500 hover:text-gray-700 flex items-center"
                  >
                    <DocumentDuplicateIcon className="h-4 w-4 mr-1" />
                    Copy JSON
                  </button>
                )}
              </div>

              {tool.parameters && tool.parameters.properties ? (
                <MCPParameterForm
                  parameters={tool.parameters}
                  values={parameters}
                  onChange={handleParameterChange}
                />
              ) : (
                <p className="text-sm text-gray-500">
                  This tool doesn't require any parameters
                </p>
              )}

              <div className="pt-4">
                <button
                  onClick={handleExecute}
                  disabled={executing}
                  className={`w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
                    executing
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500'
                  }`}
                >
                  {executing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Executing...
                    </>
                  ) : (
                    <>
                      <PlayIcon className="h-4 w-4 mr-2" />
                      Execute Tool
                    </>
                  )}
                </button>
              </div>

              {executionTime !== null && (
                <div className="text-sm text-center text-gray-500">
                  Execution time: {executionTime.toFixed(2)}s
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Response */}
          <div className="w-1/2 overflow-y-auto p-6 bg-gray-50">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900">Response</h3>
                {response && (
                  <button
                    onClick={handleCopyResponse}
                    className="text-sm text-gray-500 hover:text-gray-700 flex items-center"
                  >
                    <DocumentDuplicateIcon className="h-4 w-4 mr-1" />
                    Copy Response
                  </button>
                )}
              </div>

              {error ? (
                <div className="rounded-md bg-red-50 p-4">
                  <div className="flex">
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-red-800">
                        Execution Error
                      </h3>
                      <div className="mt-2 text-sm text-red-700">
                        <pre className="whitespace-pre-wrap">{error}</pre>
                      </div>
                    </div>
                  </div>
                </div>
              ) : response ? (
                <MCPResponseViewer response={response} />
              ) : (
                <div className="text-center py-12">
                  <PlayIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    No response yet
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Execute the tool to see the response
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MCPToolExecutor;