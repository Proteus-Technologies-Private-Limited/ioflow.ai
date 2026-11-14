import React, { useState, useEffect } from 'react';
import { InformationCircleIcon } from '@heroicons/react/24/outline';
import { scheduleToCron } from '../../utils/scheduleUtils';

const CronExpressionBuilder = ({ value, onChange, disabled = false }) => {
  // Ensure value is always a string (schedule objects such as intervals are converted)
  const cronValue = scheduleToCron(value) || '';
  const [mode, setMode] = useState('preset'); // 'preset', 'custom', or 'advanced'
  const [preset, setPreset] = useState('daily');
  const [customSchedule, setCustomSchedule] = useState({
    minute: '0',
    hour: '0',
    dayOfMonth: '*',
    month: '*',
    dayOfWeek: '*',
    time: '00:00',
    weekday: '1', // Monday
    monthDay: '1',
    type: 'daily', // default type
    intervalValue: '5',
    intervalUnit: 'minutes',
  });

  // Common presets
  const presets = [
    { value: 'every-minute', label: 'Every minute', cron: '* * * * *' },
    { value: 'every-5-minutes', label: 'Every 5 minutes', cron: '*/5 * * * *' },
    { value: 'every-15-minutes', label: 'Every 15 minutes', cron: '*/15 * * * *' },
    { value: 'every-30-minutes', label: 'Every 30 minutes', cron: '*/30 * * * *' },
    { value: 'hourly', label: 'Every hour', cron: '0 * * * *' },
    { value: 'daily', label: 'Every day at midnight', cron: '0 0 * * *' },
    { value: 'daily-morning', label: 'Every day at 9 AM', cron: '0 9 * * *' },
    { value: 'daily-evening', label: 'Every day at 6 PM', cron: '0 18 * * *' },
    { value: 'weekly', label: 'Every Monday at 9 AM', cron: '0 9 * * 1' },
    { value: 'monthly', label: 'First day of month at midnight', cron: '0 0 1 * *' },
    { value: 'weekdays', label: 'Every weekday at 9 AM', cron: '0 9 * * 1-5' },
    { value: 'weekends', label: 'Every weekend at 10 AM', cron: '0 10 * * 0,6' },
  ];

  const weekdays = [
    { value: '0', label: 'Sunday' },
    { value: '1', label: 'Monday' },
    { value: '2', label: 'Tuesday' },
    { value: '3', label: 'Wednesday' },
    { value: '4', label: 'Thursday' },
    { value: '5', label: 'Friday' },
    { value: '6', label: 'Saturday' },
  ];

  // Initialize mode from value only once on mount
  const [initialized, setInitialized] = useState(false);
  
  useEffect(() => {
    // Only initialize once when component mounts or when switching between nodes
    if (!initialized && cronValue) {
      // Check if it matches a preset
      const matchedPreset = presets.find(p => p.cron === cronValue);
      if (matchedPreset) {
        setMode('preset');
        setPreset(matchedPreset.value);
      } else {
        // Try to parse the cron expression
        const parts = cronValue.split(' ');
        if (parts.length === 5) {
          // Only set to advanced for initial load, not when user is actively editing
          setMode('advanced');
        }
      }
      setInitialized(true);
    }
  }, [cronValue, initialized]);

  // Generate cron expression from custom schedule
  const generateCronFromCustom = () => {
    if (mode === 'custom') {
      switch (customSchedule.type) {
        case 'daily':
          const [hour, minute] = customSchedule.time.split(':');
          return `${minute} ${hour} * * *`;
        case 'weekly':
          const [wHour, wMinute] = customSchedule.time.split(':');
          return `${wMinute} ${wHour} * * ${customSchedule.weekday}`;
        case 'monthly':
          const [mHour, mMinute] = customSchedule.time.split(':');
          return `${mMinute} ${mHour} ${customSchedule.monthDay} * *`;
        case 'interval':
          if (customSchedule.intervalUnit === 'minutes') {
            return `*/${customSchedule.intervalValue} * * * *`;
          } else if (customSchedule.intervalUnit === 'hours') {
            return `0 */${customSchedule.intervalValue} * * *`;
          }
          break;
      }
    }
    return cronValue || '* * * * *';
  };

  // Handle mode change
  const handleModeChange = (newMode) => {
    setMode(newMode);
    if (newMode === 'preset' && preset) {
      const presetCron = presets.find(p => p.value === preset)?.cron;
      if (presetCron) onChange(presetCron);
    }
  };

  // Handle preset change
  const handlePresetChange = (presetValue) => {
    setPreset(presetValue);
    const presetCron = presets.find(p => p.value === presetValue)?.cron;
    if (presetCron) onChange(presetCron);
  };

  // Handle custom schedule change
  const handleCustomChange = (field, newValue) => {
    const newSchedule = { ...customSchedule, [field]: newValue };
    setCustomSchedule(newSchedule);
    
    // Generate and update cron
    if (mode === 'custom') {
      // Generate cron based on the updated schedule
      let cron = '* * * * *';
      
      switch (newSchedule.type) {
        case 'daily':
          const [hour, minute] = newSchedule.time.split(':');
          cron = `${minute} ${hour} * * *`;
          break;
        case 'weekly':
          const [wHour, wMinute] = newSchedule.time.split(':');
          cron = `${wMinute} ${wHour} * * ${newSchedule.weekday}`;
          break;
        case 'monthly':
          const [mHour, mMinute] = newSchedule.time.split(':');
          cron = `${mMinute} ${mHour} ${newSchedule.monthDay} * *`;
          break;
        case 'interval':
          if (newSchedule.intervalUnit === 'minutes') {
            cron = `*/${newSchedule.intervalValue} * * * *`;
          } else if (newSchedule.intervalUnit === 'hours') {
            cron = `0 */${newSchedule.intervalValue} * * *`;
          }
          break;
      }
      
      onChange(cron);
    }
  };

  // Parse cron to human readable
  const getCronDescription = (cronExp) => {
    if (!cronExp) return 'Not configured';
    
    // Handle if cronExp is an object (from backend)
    let cronString = cronExp;
    if (typeof cronExp === 'object' && cronExp.cron_expression) {
      cronString = cronExp.cron_expression;
    }
    
    if (!cronString || typeof cronString !== 'string') return 'Not configured';
    
    const preset = presets.find(p => p.cron === cronString);
    if (preset) return preset.label;
    
    const parts = cronString.split(' ');
    if (parts.length !== 5) return 'Invalid expression';
    
    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
    
    // Try to generate a description
    let desc = 'Runs ';
    
    if (minute === '*' && hour === '*') {
      desc += 'every minute';
    } else if (minute.startsWith('*/')) {
      desc += `every ${minute.substring(2)} minutes`;
    } else if (hour === '*') {
      desc += `every hour at minute ${minute}`;
    } else if (dayOfWeek === '*' && dayOfMonth === '*') {
      desc += `daily at ${hour}:${minute.padStart(2, '0')}`;
    } else if (dayOfWeek !== '*') {
      const days = dayOfWeek.split(',').map(d => weekdays.find(w => w.value === d)?.label || d).join(', ');
      desc += `on ${days} at ${hour}:${minute.padStart(2, '0')}`;
    } else if (dayOfMonth !== '*') {
      desc += `on day ${dayOfMonth} of the month at ${hour}:${minute.padStart(2, '0')}`;
    }
    
    return desc;
  };

  return (
    <div className="space-y-4">
      {/* Mode selector */}
      <div className="flex space-x-2 border-b">
        <button
          type="button"
          onClick={() => handleModeChange('preset')}
          className={`px-3 py-2 text-sm font-medium ${
            mode === 'preset'
              ? 'border-b-2 border-blue-500 text-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          disabled={disabled}
        >
          Common Schedules
        </button>
        <button
          type="button"
          onClick={() => handleModeChange('custom')}
          className={`px-3 py-2 text-sm font-medium ${
            mode === 'custom'
              ? 'border-b-2 border-blue-500 text-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          disabled={disabled}
        >
          Custom Schedule
        </button>
        <button
          type="button"
          onClick={() => handleModeChange('advanced')}
          className={`px-3 py-2 text-sm font-medium ${
            mode === 'advanced'
              ? 'border-b-2 border-blue-500 text-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          disabled={disabled}
        >
          Advanced (Cron)
        </button>
      </div>

      {/* Preset mode */}
      {mode === 'preset' && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Select a schedule
          </label>
          <select
            value={preset}
            onChange={(e) => handlePresetChange(e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {presets.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Custom mode */}
      {mode === 'custom' && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Schedule Type
            </label>
            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="radio"
                  name="scheduleType"
                  value="interval"
                  checked={customSchedule.type === 'interval'}
                  onChange={(e) => handleCustomChange('type', e.target.value)}
                  disabled={disabled}
                  className="mr-2"
                />
                <span className="text-sm">Run at intervals</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  name="scheduleType"
                  value="daily"
                  checked={customSchedule.type === 'daily'}
                  onChange={(e) => handleCustomChange('type', e.target.value)}
                  disabled={disabled}
                  className="mr-2"
                />
                <span className="text-sm">Run daily</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  name="scheduleType"
                  value="weekly"
                  checked={customSchedule.type === 'weekly'}
                  onChange={(e) => handleCustomChange('type', e.target.value)}
                  disabled={disabled}
                  className="mr-2"
                />
                <span className="text-sm">Run weekly</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  name="scheduleType"
                  value="monthly"
                  checked={customSchedule.type === 'monthly'}
                  onChange={(e) => handleCustomChange('type', e.target.value)}
                  disabled={disabled}
                  className="mr-2"
                />
                <span className="text-sm">Run monthly</span>
              </label>
            </div>
          </div>

          {/* Interval options */}
          {customSchedule.type === 'interval' && (
            <div className="flex items-center space-x-2">
              <span className="text-sm">Every</span>
              <input
                type="number"
                min="1"
                max="60"
                value={customSchedule.intervalValue || '5'}
                onChange={(e) => handleCustomChange('intervalValue', e.target.value)}
                disabled={disabled}
                className="w-16 px-2 py-1 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <select
                value={customSchedule.intervalUnit || 'minutes'}
                onChange={(e) => handleCustomChange('intervalUnit', e.target.value)}
                disabled={disabled}
                className="px-2 py-1 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="minutes">minutes</option>
                <option value="hours">hours</option>
              </select>
            </div>
          )}

          {/* Time picker for daily/weekly/monthly */}
          {(customSchedule.type === 'daily' || 
            customSchedule.type === 'weekly' || 
            customSchedule.type === 'monthly') && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Time
              </label>
              <input
                type="time"
                value={customSchedule.time}
                onChange={(e) => handleCustomChange('time', e.target.value)}
                disabled={disabled}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Weekday selector for weekly */}
          {customSchedule.type === 'weekly' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Day of week
              </label>
              <select
                value={customSchedule.weekday}
                onChange={(e) => handleCustomChange('weekday', e.target.value)}
                disabled={disabled}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {weekdays.map((day) => (
                  <option key={day.value} value={day.value}>
                    {day.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Day of month for monthly */}
          {customSchedule.type === 'monthly' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Day of month
              </label>
              <input
                type="number"
                min="1"
                max="31"
                value={customSchedule.monthDay}
                onChange={(e) => handleCustomChange('monthDay', e.target.value)}
                disabled={disabled}
                className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          )}
        </div>
      )}

      {/* Advanced mode */}
      {mode === 'advanced' && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Cron Expression
          </label>
          <input
            type="text"
            value={cronValue}
            onChange={(e) => onChange(e.target.value)}
            placeholder="* * * * *"
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
          />
          <div className="flex items-start space-x-1 text-xs text-gray-500">
            <InformationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              <p>Format: minute hour day month weekday</p>
              <p>Example: 0 9 * * 1-5 (weekdays at 9 AM)</p>
              <p>Use * for any, */n for intervals, n,m for lists, n-m for ranges</p>
            </div>
          </div>
        </div>
      )}

      {/* Preview */}
      <div className="bg-gray-50 rounded-md p-3">
        <div className="text-sm">
          <span className="font-medium text-gray-700">Schedule: </span>
          <span className="text-gray-900">{getCronDescription(cronValue)}</span>
        </div>
        {cronValue && (
          <div className="text-xs text-gray-500 mt-1 font-mono">
            Cron: {cronValue}
          </div>
        )}
      </div>
    </div>
  );
};

export default CronExpressionBuilder;