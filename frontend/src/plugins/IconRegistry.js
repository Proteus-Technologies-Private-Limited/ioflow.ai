/**
 * Centralized Icon Registry
 *
 * Single source of truth for category -> icon component mapping.
 * Replaces duplicated switches in ApplicationServiceSelector, ActionNode, TriggerNode.
 *
 * Extensible: plugins can call registerIcon() to add new mappings.
 */
import {
  BoltIcon,
  ClockIcon,
  CursorArrowRaysIcon,
  GlobeAltIcon,
  CodeBracketIcon,
  FolderIcon,
  ChatBubbleLeftRightIcon,
  CubeIcon,
  CircleStackIcon,
  EnvelopeIcon,
  CloudIcon,
  CpuChipIcon,
  DocumentIcon,
  CogIcon,
  SignalIcon,
} from '@heroicons/react/24/outline';

// ─── Category / app_type -> Icon Component ───

const categoryIcons = {
  // app_type values
  'database': CircleStackIcon,
  'email': EnvelopeIcon,

  // category values
  'Database': CircleStackIcon,
  'Communication': ChatBubbleLeftRightIcon,
  'Email': EnvelopeIcon,
  'Cloud': CloudIcon,
  'Storage': CloudIcon,
  'API': GlobeAltIcon,
  'Integration': GlobeAltIcon,
  'AI': CpuChipIcon,
  'ML': CpuChipIcon,
  'Document': DocumentIcon,
  'File': DocumentIcon,
  'Automation': CogIcon,
};

const DEFAULT_ICON = CubeIcon;

// ─── Trigger type -> Icon Component ───

const triggerIcons = {
  'application_event': BoltIcon,
  'event': BoltIcon,
  'webhook': GlobeAltIcon,
  'schedule': ClockIcon,
  'file_change': FolderIcon,
  'api_call': CodeBracketIcon,
  'chat_input': ChatBubbleLeftRightIcon,
  'mqtt': SignalIcon,
};

const DEFAULT_TRIGGER_ICON = CursorArrowRaysIcon;

// ─── Public API ───

/**
 * Get icon component for an app based on app_type and category.
 * Checks app_type first, then category, then falls back to default.
 *
 * @param {string} appType - The app_type field (e.g., 'database', 'email')
 * @param {string} category - The category field (e.g., 'Database', 'AI')
 * @returns {React.ComponentType} Icon component
 */
export function getIconForCategory(appType, category) {
  if (appType && categoryIcons[appType]) {
    return categoryIcons[appType];
  }
  if (category && categoryIcons[category]) {
    return categoryIcons[category];
  }
  return DEFAULT_ICON;
}

/**
 * Get icon component for a trigger type.
 *
 * @param {string} triggerType
 * @returns {React.ComponentType} Icon component
 */
export function getIconForTriggerType(triggerType) {
  return triggerIcons[triggerType] || DEFAULT_TRIGGER_ICON;
}

/**
 * Register a custom icon for a category/app_type key.
 * Used by plugins to extend the icon system.
 *
 * @param {string} key - The category or app_type key
 * @param {React.ComponentType} component - The icon component
 */
export function registerIcon(key, component) {
  categoryIcons[key] = component;
}

/**
 * Register a custom icon for a trigger type.
 *
 * @param {string} triggerType
 * @param {React.ComponentType} component
 */
export function registerTriggerIcon(triggerType, component) {
  triggerIcons[triggerType] = component;
}

export default {
  getIconForCategory,
  getIconForTriggerType,
  registerIcon,
  registerTriggerIcon,
};
