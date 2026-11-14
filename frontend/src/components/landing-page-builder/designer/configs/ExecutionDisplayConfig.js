import React from 'react';

const DISPLAY_MODES = [
  { value: 'minimal_steps', label: 'Minimal Steps', description: 'Compact spinner + progress bar + log list' },
  { value: 'standard_steps', label: 'Standard Steps', description: 'Node cards with type icons, timing, and status' },
  { value: 'standard', label: 'Standard', description: 'Full IOFlow-style with currently executing banner + node cards' },
  { value: 'flow_only', label: 'Flow Only', description: 'Visual node flow with pill badges showing progression' },
  { value: 'flow_with_steps', label: 'Flow + Steps', description: 'Node flow visualization above detailed step cards' },
  { value: 'flow_design', label: 'Flow Design', description: 'Full flow diagram with zoom-to-node as each step executes' },
  { value: 'flow_design_steps', label: 'Flow Design + Steps (Stacked)', description: 'Flow diagram with zoom-to-node above detailed step cards' },
  { value: 'flow_design_side_by_side', label: 'Flow Design + Steps (Side by Side)', description: 'Flow diagram on the left, step cards on the right — like the default IOFlow layout' },
];

export default function ExecutionDisplayConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Execution Display</h3>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Execution Progress"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Display Mode */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Display Mode</label>
        <div className="space-y-2">
          {DISPLAY_MODES.map((mode) => (
            <label
              key={mode.value}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                (config.displayMode || 'minimal_steps') === mode.value
                  ? 'border-primary bg-primary/5'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <input
                type="radio"
                name="displayMode"
                value={mode.value}
                checked={(config.displayMode || 'minimal_steps') === mode.value}
                onChange={(e) => onChange({ ...config, displayMode: e.target.value })}
                className="mt-0.5 text-primary focus:ring-primary"
              />
              <div>
                <div className="text-sm font-medium text-gray-800">{mode.label}</div>
                <div className="text-xs text-gray-500">{mode.description}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Visibility Options */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Visibility</label>
        <div className="space-y-2">
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.showOnlyWhenRunning || false}
              onChange={(e) => onChange({ ...config, showOnlyWhenRunning: e.target.checked })}
              className="mt-0.5 rounded text-primary focus:ring-primary"
            />
            <div>
              <span className="text-sm text-gray-700">Show only when execution starts</span>
              <p className="text-xs text-gray-500">Hidden until the user submits the form</p>
            </div>
          </label>
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.hideAfterComplete || false}
              onChange={(e) => onChange({ ...config, hideAfterComplete: e.target.checked })}
              className="mt-0.5 rounded text-primary focus:ring-primary"
            />
            <div>
              <span className="text-sm text-gray-700">Hide after execution completes</span>
              <p className="text-xs text-gray-500">Disappears once finished (pair with a separate Result Display block)</p>
            </div>
          </label>
        </div>
      </div>

      {/* Show Review Task */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Human Review</label>
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={config.showReviewTask || false}
            onChange={(e) => onChange({ ...config, showReviewTask: e.target.checked })}
            className="mt-0.5 rounded text-primary focus:ring-primary"
          />
          <div>
            <span className="text-sm text-gray-700">Show review task button</span>
            <p className="text-xs text-gray-500">When enabled, a "Complete Task" button appears when the flow pauses for human review</p>
          </div>
        </label>
      </div>

      {/* Show Logs (for minimal_steps mode) */}
      {(config.displayMode || 'minimal_steps') === 'minimal_steps' && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={config.showLogs !== false}
            onChange={(e) => onChange({ ...config, showLogs: e.target.checked })}
            className="rounded text-primary focus:ring-primary"
          />
          <span className="text-sm text-gray-700">Show execution logs</span>
        </label>
      )}
    </div>
  );
}
