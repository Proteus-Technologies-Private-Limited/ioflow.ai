import React from 'react';
import ApplicationEventSelector from './ApplicationEventSelector';

const WaitForEventConfig = ({
  node,
  updateNodeData,
  availableVariables,
  applications = [],
  events = [],
  loadingEvents = false,
}) => {
  const data = node.data || {};
  const appId = data.appId || '';
  const eventName = data.eventName || '';
  const eventId = data.eventId || '';
  const matchMode = data.matchMode || 'token';
  const correlationConfig = data.correlationConfig || { eventField: '', flowField: '' };
  const timeoutMinutes = data.timeoutMinutes || 0;
  const timeoutAction = data.timeoutAction || 'fail';
  const defaultData = data.defaultData || {};

  // Check validation errors to determine if correlation is mandatory
  const validationErrors = data.validationErrors || [];
  const matchModeError = validationErrors.find(e => e.field === 'matchMode');
  const correlationRequired = !!matchModeError;

  const update = (key, value) => {
    updateNodeData(node.id, { [key]: value });
  };

  const getVariableOptions = () => {
    if (!availableVariables) return [];
    const options = [];
    if (Array.isArray(availableVariables)) {
      availableVariables.forEach(v => {
        if (typeof v === 'string') {
          options.push(v);
        } else if (v.path) {
          options.push(v.path);
        }
      });
    }
    return options;
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-900">Wait for Event Configuration</h3>

      {/* Application & Event Selector */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Application & Event
        </label>
        <ApplicationEventSelector
          applications={applications}
          events={events}
          selectedAppId={appId}
          selectedEventId={eventId}
          selectedEventName={eventName}
          onApplicationSelect={(selectedAppId) => {
            update('appId', selectedAppId);
          }}
          onEventSelect={(event) => {
            update('eventName', event.event_name);
            update('eventId', event.event_id || '');
          }}
          loadingEvents={loadingEvents}
        />
      </div>

      {/* Match Mode */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <label className="block text-sm font-medium text-gray-700">Match Mode</label>
          {correlationRequired ? (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-100 text-red-700">
              Required
            </span>
          ) : (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
              Optional
            </span>
          )}
        </div>

        {correlationRequired && (
          <div className="mb-2 p-2 bg-red-50 border border-red-200 rounded-md">
            <p className="text-xs text-red-700">
              {matchModeError.message}
            </p>
          </div>
        )}

        <div className="flex gap-4">
          <label className={`flex items-center gap-2 text-sm ${correlationRequired && matchMode === 'token' ? 'text-red-600' : ''}`}>
            <input
              type="radio"
              name={`matchMode-${node.id}`}
              value="token"
              checked={matchMode === 'token'}
              onChange={() => update('matchMode', 'token')}
              className="text-amber-600"
              disabled={correlationRequired}
            />
            Callback Token
            {correlationRequired && <span className="text-[10px] text-red-500">(unavailable)</span>}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name={`matchMode-${node.id}`}
              value="correlation"
              checked={matchMode === 'correlation'}
              onChange={() => update('matchMode', 'correlation')}
              className="text-amber-600"
            />
            Correlation
            {correlationRequired && <span className="text-[10px] text-red-500">*</span>}
          </label>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {matchMode === 'token'
            ? 'A unique callback token is generated. The external system must include it when sending the event.'
            : 'Match incoming events by correlating a field value (e.g., order_id) between the event and the flow.'}
        </p>
      </div>

      {/* Correlation Config */}
      {matchMode === 'correlation' && (
        <div className="space-y-3 pl-2 border-l-2 border-amber-200">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Event Field
            </label>
            <input
              type="text"
              value={correlationConfig.eventField || ''}
              onChange={(e) => update('correlationConfig', {
                ...correlationConfig,
                eventField: e.target.value
              })}
              placeholder="e.g., order_id or data.order.id"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">Field path in the incoming event data (supports dot notation)</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Flow Value
            </label>
            <input
              type="text"
              value={correlationConfig.flowField || ''}
              onChange={(e) => update('correlationConfig', {
                ...correlationConfig,
                flowField: e.target.value
              })}
              placeholder="e.g., {{node_outputs.trigger.order_id}}"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            {getVariableOptions().length > 0 && (
              <div className="mt-1">
                <p className="text-xs text-gray-500 mb-1">Available variables:</p>
                <div className="flex flex-wrap gap-1">
                  {getVariableOptions().slice(0, 10).map(v => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => update('correlationConfig', {
                        ...correlationConfig,
                        flowField: `{{${v}}}`
                      })}
                      className="text-[10px] px-1.5 py-0.5 bg-gray-100 hover:bg-gray-200 rounded text-gray-600"
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Timeout */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Timeout (minutes)
        </label>
        <input
          type="number"
          value={timeoutMinutes}
          onChange={(e) => update('timeoutMinutes', parseInt(e.target.value) || 0)}
          min={0}
          placeholder="0 = no timeout"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
        />
        <p className="text-xs text-gray-500 mt-1">Set to 0 for no timeout (wait indefinitely)</p>
      </div>

      {/* Timeout Action */}
      {timeoutMinutes > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            On Timeout
          </label>
          <select
            value={timeoutAction}
            onChange={(e) => update('timeoutAction', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="fail">Fail execution</option>
            <option value="continue_with_defaults">Continue with default data</option>
            <option value="skip">Skip (continue with empty data)</option>
          </select>
        </div>
      )}

      {/* Default Data */}
      {timeoutMinutes > 0 && timeoutAction === 'continue_with_defaults' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Default Data (JSON)
          </label>
          <textarea
            value={typeof defaultData === 'object' ? JSON.stringify(defaultData, null, 2) : defaultData}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                update('defaultData', parsed);
              } catch {
                update('defaultData', e.target.value);
              }
            }}
            rows={4}
            placeholder='{"status": "timeout", "message": "Event not received"}'
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">Data to inject into the flow if the event times out</p>
        </div>
      )}
    </div>
  );
};

export default WaitForEventConfig;
