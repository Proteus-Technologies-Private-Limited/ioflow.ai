import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  PlayIcon, 
  PauseIcon, 
  ForwardIcon,
  StopIcon,
  ChevronRightIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';

const TransformDebugger = ({ 
  nodeId, 
  script, 
  executionId,
  websocket,
  onClose 
}) => {
  const [debugState, setDebugState] = useState(null);
  const [lines, setLines] = useState([]);
  const [currentLine, setCurrentLine] = useState(0);
  const [breakpoints, setBreakpoints] = useState(new Set());
  const [variables, setVariables] = useState({});
  const [isRunning, setIsRunning] = useState(false);
  const [expandedVars, setExpandedVars] = useState(new Set(['input', 'output', 'local']));
  const codeContainerRef = useRef(null);
  const currentLineRef = useRef(null);

  // Parse script into lines
  useEffect(() => {
    if (script) {
      const scriptLines = script.split('\n');
      setLines(scriptLines);
    }
  }, [script]);

  // Auto-scroll to current line when it changes
  useEffect(() => {
    if (currentLineRef.current && codeContainerRef.current) {
      // Scroll the current line into view with smooth behavior
      currentLineRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }
  }, [currentLine]);

  // Step to next line
  const handleStep = useCallback(() => {
    console.log('Step button clicked');
    console.log('WebSocket available:', !!websocket);
    console.log('Node ID:', nodeId);
    
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      setIsRunning(true);
      const message = {
        action: 'transform_step',
        node_id: nodeId
      };
      console.log('Sending step message:', message);
      try {
        websocket.send(JSON.stringify(message));
      } catch (error) {
        console.error('Error sending step message:', error);
        setIsRunning(false);
        // If WebSocket error, close the debugger
        if (error.name === 'InvalidStateError' || websocket.readyState !== WebSocket.OPEN) {
          console.log('WebSocket closed, closing debugger');
          if (onClose) {
            onClose();
          }
        }
      }
    } else {
      console.error('WebSocket not available or not open. State:', websocket?.readyState);
      // If WebSocket is closed, close the debugger
      if (websocket && websocket.readyState === WebSocket.CLOSED) {
        console.log('WebSocket closed, closing debugger');
        if (onClose) {
          onClose();
        }
      }
    }
  }, [websocket, nodeId, onClose]);

  // Continue execution
  const handleContinue = useCallback(() => {
    console.log('Continue button clicked');
    console.log('WebSocket available:', !!websocket);
    console.log('Node ID:', nodeId);
    
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      setIsRunning(true);
      const message = {
        action: 'transform_continue',
        node_id: nodeId
      };
      console.log('Sending continue message:', message);
      try {
        websocket.send(JSON.stringify(message));
        
        // Set a timeout to stop spinning if no response
        setTimeout(() => {
          setIsRunning(current => {
            if (current) {
              console.warn('Continue operation timed out, stopping spinner');
              return false;
            }
            return current;
          });
        }, 10000); // 10 second timeout
      } catch (error) {
        console.error('Error sending continue message:', error);
        setIsRunning(false);
        // If WebSocket error, close the debugger
        if (error.name === 'InvalidStateError' || websocket.readyState !== WebSocket.OPEN) {
          console.log('WebSocket closed, closing debugger');
          if (onClose) {
            onClose();
          }
        }
      }
    } else {
      console.error('WebSocket not available or not open. State:', websocket?.readyState);
      setIsRunning(false);
      // If WebSocket is closed, close the debugger
      if (websocket && websocket.readyState === WebSocket.CLOSED) {
        console.log('WebSocket closed, closing debugger');
        if (onClose) {
          onClose();
        }
      }
    }
  }, [websocket, nodeId, onClose]);

  // Monitor WebSocket state
  useEffect(() => {
    if (websocket) {
      const handleClose = () => {
        console.log('WebSocket closed in TransformDebugger');
        setIsRunning(false);
        // Auto-close the debugger if WebSocket closes
        if (onClose) {
          setTimeout(() => {
            console.log('Auto-closing TransformDebugger due to WebSocket closure');
            onClose();
          }, 100);
        }
      };

      const handleError = (error) => {
        console.error('WebSocket error in TransformDebugger:', error);
        setIsRunning(false);
      };

      // Add event listeners
      websocket.addEventListener('close', handleClose);
      websocket.addEventListener('error', handleError);

      // Cleanup
      return () => {
        websocket.removeEventListener('close', handleClose);
        websocket.removeEventListener('error', handleError);
      };
    }
  }, [websocket, onClose]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'F11' || (e.key === 's' && e.ctrlKey)) {
        e.preventDefault();
        handleStep();
      } else if (e.key === 'F5' || (e.key === 'c' && e.ctrlKey)) {
        e.preventDefault();
        handleContinue();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleStep, handleContinue]);

  // Listen for WebSocket messages
  useEffect(() => {
    if (!websocket) return;

    const handleMessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('TransformDebugger received message:', message);
      console.log('Message type:', message.type);
      console.log('Message node_id:', message.node_id);
      console.log('Current nodeId:', nodeId);
      
      switch (message.type) {
        case 'transform_debug_start':
          console.log('Transform debug start received');
          if (message.node_id === nodeId) {
            console.log('Node ID matches!');
            console.log('Debug info:', message.debug_info);
            console.log('Variables in debug_info:', message.debug_info?.variables);
            setDebugState(message.debug_info);
            setCurrentLine(message.debug_info.current_line || 0);
            setVariables(message.debug_info.variables || {});
            console.log('Variables set to:', message.debug_info.variables || {});
          } else {
            console.log('Node ID mismatch - ignoring');
          }
          break;
          
        case 'transform_step_result':
          if (message.node_id === nodeId && message.result) {
            const result = message.result;
            console.log('Step result received:', result);
            console.log('Current line from result:', result.current_line);
            
            // Update current line - make sure we handle both number and undefined
            if (typeof result.current_line === 'number') {
              setCurrentLine(result.current_line);
              console.log('Updated current line to:', result.current_line);
            }
            
            setVariables(result.variables || {});
            setIsRunning(result.status === 'running');
            
            if (result.status === 'completed') {
              setIsRunning(false);
              console.log('Transform debugging completed, closing debugger');
              // Close the debugger and pass the output
              if (onClose) {
                onClose(result.output);
              }
            } else if (result.status === 'error') {
              setIsRunning(false);
              console.error('Transform error:', result.error);
              console.error('Error at line:', result.line);
            }
          }
          break;
          
        case 'transform_continue_result':
          if (message.node_id === nodeId && message.result) {
            const result = message.result;
            console.log('Continue result received:', result);
            
            // Update current line if provided
            if (typeof result.current_line === 'number') {
              setCurrentLine(result.current_line);
            }
            
            // Update variables
            setVariables(result.variables || {});
            
            // Always set running to false after continue completes
            setIsRunning(false);
            
            // Check completion status
            if (result.status === 'completed') {
              console.log('Transform completed via continue, closing debugger');
              if (onClose) {
                onClose(result.output);
              }
            } else if (result.status === 'paused') {
              console.log('Transform paused at breakpoint or line:', result.current_line);
              // Already set isRunning to false above
            } else if (result.status === 'error') {
              console.error('Transform error during continue:', result.error);
              // Already set isRunning to false above
            }
          }
          break;
          
        case 'transform_state':
          if (message.node_id === nodeId && message.state) {
            console.log('Transform state received, setting variables:', message.state.variables);
            setDebugState(message.state);
            setCurrentLine(message.state.current_line || 0);
            const vars = message.state.variables || {};
            console.log('About to setVariables with:', vars);
            setVariables(vars);
            console.log('Variables should now be:', vars);
            setBreakpoints(new Set(message.state.breakpoints || []));
          }
          break;
      }
    };

    websocket.addEventListener('message', handleMessage);
    
    // Request initial state
    console.log('Requesting initial transform state for node:', nodeId);
    websocket.send(JSON.stringify({
      action: 'transform_get_state',
      node_id: nodeId
    }));

    return () => {
      websocket.removeEventListener('message', handleMessage);
    };
  }, [websocket, nodeId, onClose]);

  // Toggle breakpoint
  const toggleBreakpoint = useCallback((lineNo) => {
    const newBreakpoints = new Set(breakpoints);
    const action = newBreakpoints.has(lineNo) ? 
      'transform_remove_breakpoint' : 'transform_set_breakpoint';
    
    if (newBreakpoints.has(lineNo)) {
      newBreakpoints.delete(lineNo);
    } else {
      newBreakpoints.add(lineNo);
    }
    
    setBreakpoints(newBreakpoints);
    
    if (websocket) {
      websocket.send(JSON.stringify({
        action,
        node_id: nodeId,
        line_no: lineNo
      }));
    }
  }, [websocket, nodeId, breakpoints]);

  // Toggle variable group expansion
  const toggleVarExpansion = (group) => {
    const newExpanded = new Set(expandedVars);
    if (newExpanded.has(group)) {
      newExpanded.delete(group);
    } else {
      newExpanded.add(group);
    }
    setExpandedVars(newExpanded);
  };

  // Render variable value
  const renderValue = (value, depth = 0) => {
    if (value === null) return <span className="text-gray-500">null</span>;
    if (value === undefined) return <span className="text-gray-500">undefined</span>;
    
    if (typeof value === 'object') {
      if (Array.isArray(value)) {
        if (depth > 2) return <span className="text-blue-500">[Array({value.length})]</span>;
        return (
          <div className="ml-4">
            <span className="text-blue-500">[</span>
            {value.map((item, idx) => (
              <div key={idx} className="ml-4">
                <span className="text-gray-400">{idx}:</span> {renderValue(item, depth + 1)}
              </div>
            ))}
            <span className="text-blue-500">]</span>
          </div>
        );
      } else {
        const keys = Object.keys(value);
        if (depth > 2 || keys.length > 10) {
          return <span className="text-blue-500">{`{Object(${keys.length} keys)}`}</span>;
        }
        return (
          <div className="ml-4">
            <span className="text-blue-500">{'{'}</span>
            {keys.map(key => (
              <div key={key} className="ml-4">
                <span className="text-purple-400">{key}:</span> {renderValue(value[key], depth + 1)}
              </div>
            ))}
            <span className="text-blue-500">{'}'}</span>
          </div>
        );
      }
    }
    
    if (typeof value === 'string') {
      return <span className="text-green-500">"{value}"</span>;
    }
    
    if (typeof value === 'number') {
      return <span className="text-yellow-500">{value}</span>;
    }
    
    if (typeof value === 'boolean') {
      return <span className="text-orange-500">{value.toString()}</span>;
    }
    
    return <span className="text-gray-300">{String(value)}</span>;
  };

  return (
    <div className="flex h-full w-full bg-gray-900 text-white">
      {/* Code Editor Panel */}
      <div className="flex-1 flex flex-col" style={{ minWidth: '0' }}>
        {/* Toolbar */}
        <div className="flex items-center gap-2 p-2 bg-gray-800 border-b border-gray-700">
          <button
            onClick={handleStep}
            disabled={isRunning}
            className="p-2 rounded hover:bg-gray-700 disabled:opacity-50 transition-colors"
            title="Step Into (F11 or Ctrl+S)"
          >
            <ChevronRightIcon className="h-5 w-5" />
          </button>
          <button
            onClick={handleContinue}
            disabled={isRunning}
            className="p-2 rounded hover:bg-gray-700 disabled:opacity-50 transition-colors"
            title="Continue (F5 or Ctrl+C)"
          >
            <PlayIcon className="h-5 w-5" />
          </button>
          <button
            onClick={() => onClose && onClose()}
            className="p-2 rounded hover:bg-gray-700 transition-colors"
            title="Stop Debugging"
          >
            <StopIcon className="h-5 w-5" />
          </button>
          
          <div className="h-6 w-px bg-gray-600" />
          
          {/* Execution Status */}
          <div className="flex items-center gap-2">
            {isRunning && (
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-yellow-400"></div>
                <span className="text-sm text-yellow-400">Running</span>
              </div>
            )}
          </div>
          
          <div className="flex-1" />
          
          {/* Current Line Indicator */}
          <div className="flex items-center gap-2 px-3 py-1 bg-gray-700 rounded">
            <span className="text-sm text-gray-400">Line:</span>
            <span className="text-sm font-bold text-yellow-400">{currentLine + 1}</span>
            <span className="text-sm text-gray-400">/ {lines.length}</span>
          </div>
          
          {/* Code Preview of Current Line */}
          {lines[currentLine] && (
            <div className="max-w-xs overflow-hidden">
              <code className="text-xs text-gray-300 truncate block px-2 py-1 bg-gray-700 rounded">
                {lines[currentLine].trim()}
              </code>
            </div>
          )}
        </div>

        {/* Code Display */}
        <div className="flex-1 overflow-auto p-4 font-mono text-sm" ref={codeContainerRef}>
          {lines.map((line, idx) => (
            <div
              key={idx}
              ref={idx === currentLine ? currentLineRef : null}
              className={`flex items-start transition-all duration-200 ${
                idx === currentLine 
                  ? 'bg-yellow-500 bg-opacity-20 border-l-4 border-yellow-400 shadow-lg' 
                  : 'border-l-4 border-transparent'
              }`}
              style={{
                minHeight: '24px',
                paddingTop: '2px',
                paddingBottom: '2px'
              }}
            >
              {/* Breakpoint Column */}
              <div 
                className="w-8 flex-shrink-0 text-right pr-2 cursor-pointer select-none"
                onClick={() => toggleBreakpoint(idx)}
              >
                {breakpoints.has(idx) && (
                  <span className="text-red-500">●</span>
                )}
              </div>
              
              {/* Line Number */}
              <div className={`w-12 flex-shrink-0 text-right pr-4 select-none ${
                idx === currentLine ? 'text-yellow-400 font-bold' : 'text-gray-500'
              }`}>
                {idx + 1}
              </div>
              
              {/* Current Line Indicator */}
              <div className="w-4 flex-shrink-0">
                {idx === currentLine && (
                  <span className="text-yellow-400 animate-pulse">▶</span>
                )}
              </div>
              
              {/* Code Line */}
              <div className="flex-1">
                <SyntaxHighlighter
                  language="python"
                  style={tomorrow}
                  customStyle={{
                    margin: 0,
                    padding: 0,
                    background: 'transparent',
                    fontSize: 'inherit'
                  }}
                  wrapLongLines
                >
                  {line || ' '}
                </SyntaxHighlighter>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Variables Panel */}
      <div className="flex-shrink-0 w-96 flex flex-col bg-gray-800 border-l border-gray-700">
        <div className="p-3 border-b border-gray-700">
          <h3 className="font-semibold">Variables</h3>
        </div>
        
        <div className="flex-1 overflow-auto p-3 text-sm">
          {console.log('Rendering variables:', variables)}
          {console.log('Variable keys:', Object.keys(variables))}
          {console.log('Variables type:', typeof variables)}
          {console.log('Is variables an object?', variables && typeof variables === 'object')}
          {Object.keys(variables).length === 0 ? (
            <div className="text-gray-500 italic p-4">No variables to display</div>
          ) : (
            Object.entries(variables).map(([group, values]) => {
              console.log(`Rendering group ${group}:`, values);
              return (
            <div key={group} className="mb-4">
              <div 
                className="flex items-center cursor-pointer hover:bg-gray-700 p-1 rounded"
                onClick={() => toggleVarExpansion(group)}
              >
                {expandedVars.has(group) ? (
                  <ChevronDownIcon className="h-4 w-4 mr-1" />
                ) : (
                  <ChevronRightIcon className="h-4 w-4 mr-1" />
                )}
                <span className="font-semibold text-blue-400">{group}</span>
                <span className="ml-2 text-gray-500">
                  ({Object.keys(values || {}).length})
                </span>
              </div>
              
              {expandedVars.has(group) && values && (
                <div className="ml-5 mt-1">
                  {Object.keys(values).length === 0 ? (
                    <div className="text-gray-500 italic">empty</div>
                  ) : (
                    Object.entries(values).map(([key, value]) => (
                      <div key={key} className="mb-2">
                        <div className="flex items-start">
                          <span className="text-purple-400 mr-2">{key}:</span>
                          <div className="flex-1">{renderValue(value)}</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          );
          })
          )}
        </div>
      </div>
    </div>
  );
};

export default TransformDebugger;