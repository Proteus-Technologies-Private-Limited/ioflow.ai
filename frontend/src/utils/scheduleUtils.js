// Schedule trigger helpers.
//
// The backend scheduler (backend/services/scheduler.py) accepts several schedule
// shapes: {type: 'cron', cron_expression}, {type: 'interval', interval_value,
// interval_unit}, {type: 'daily', time}, {type: 'weekly', days, time} and
// {type: 'monthly', day, time}. The designer's CronExpressionBuilder only edits
// cron strings, so these helpers translate between the two.

const parseTime = (time) => {
  const match = /^(\d{1,2}):(\d{2})$/.exec(String(time || '00:00').trim());
  if (!match) return null;
  return { hour: parseInt(match[1], 10), minute: parseInt(match[2], 10) };
};

// Cron string for an interval, or null when cron cannot express it exactly
// (e.g. every 45 minutes or every 5 hours).
const intervalToCron = (value, unit) => {
  const n = parseInt(value, 10);
  if (!Number.isFinite(n) || n <= 0) return null;
  if (unit === 'minutes') {
    if (n === 1) return '* * * * *';
    if (n < 60 && 60 % n === 0) return `*/${n} * * * *`;
    if (n % 60 === 0) return intervalToCron(n / 60, 'hours');
    return null;
  }
  if (unit === 'hours') {
    if (n === 1) return '0 * * * *';
    if (n < 24 && 24 % n === 0) return `0 */${n} * * *`;
    if (n % 24 === 0) return intervalToCron(n / 24, 'days');
    return null;
  }
  if (unit === 'days') {
    return n === 1 ? '0 0 * * *' : null;
  }
  return null;
};

// Cron string equivalent of any schedule value, or null if there is none.
export const scheduleToCron = (schedule) => {
  if (!schedule) return null;
  if (typeof schedule === 'string') return schedule;
  if (typeof schedule !== 'object') return null;

  try {
    if (typeof schedule.cron_expression === 'string' && schedule.cron_expression) {
      return schedule.cron_expression;
    }
    switch (schedule.type) {
      case 'interval':
        return intervalToCron(schedule.interval_value, schedule.interval_unit || 'hours');
      case 'daily': {
        const t = parseTime(schedule.time);
        return t ? `${t.minute} ${t.hour} * * *` : null;
      }
      case 'weekly': {
        const t = parseTime(schedule.time);
        const days = Array.isArray(schedule.days) ? schedule.days : [];
        return t && days.length ? `${t.minute} ${t.hour} * * ${days.join(',')}` : null;
      }
      case 'monthly': {
        const t = parseTime(schedule.time);
        // Cron has no "last day of month"; leave that one to the backend.
        if (!t || schedule.day === 'last') return null;
        return `${t.minute} ${t.hour} ${schedule.day || 1} * *`;
      }
      default:
        return null;
    }
  } catch (err) {
    console.error('Could not convert schedule to cron:', schedule, err);
    return null;
  }
};

// Human-readable summary of a schedule object, for showing schedules that
// cron cannot represent.
export const describeSchedule = (schedule) => {
  if (!schedule) return '';
  if (typeof schedule === 'string') return schedule;
  if (typeof schedule !== 'object') return String(schedule);
  switch (schedule.type) {
    case 'interval':
      return `Every ${schedule.interval_value ?? 1} ${schedule.interval_unit || 'hours'}`;
    case 'daily':
      return `Daily at ${schedule.time || '00:00'}`;
    case 'weekly':
      return `Weekly on days ${(schedule.days || []).join(', ')} at ${schedule.time || '00:00'}`;
    case 'monthly':
      return `Monthly on day ${schedule.day ?? 1} at ${schedule.time || '00:00'}`;
    case 'cron':
      return schedule.cron_expression || '';
    default:
      return JSON.stringify(schedule);
  }
};

// Schedule as the backend expects it in trigger_config.schedule. A cron string
// from the builder becomes a cron schedule; an object the backend already
// understands (interval/daily/weekly/monthly/cron) is passed through unchanged
// so flows saved by agents keep their schedule.
export const formatScheduleForBackend = (schedule) => {
  if (!schedule) return null;
  if (typeof schedule === 'string') {
    return { type: 'cron', cron_expression: schedule };
  }
  if (typeof schedule === 'object') {
    if (schedule.cron_expression) {
      return { type: 'cron', ...schedule };
    }
    if (['interval', 'daily', 'weekly', 'monthly'].includes(schedule.type)) {
      return schedule;
    }
  }
  console.warn('Unrecognised schedule value, not saved:', schedule);
  return null;
};
