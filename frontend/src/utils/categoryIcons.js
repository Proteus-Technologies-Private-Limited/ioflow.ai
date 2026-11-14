import {
  SparklesIcon,
  DocumentTextIcon,
  CircleStackIcon,
  BellAlertIcon,
  BeakerIcon,
  GlobeAltIcon,
  FolderIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/react/24/outline';

/**
 * Category icon and color mapping for flow examples
 */
export const CATEGORY_ICONS = {
  SparklesIcon,
  DocumentTextIcon,
  CircleStackIcon,
  BellAlertIcon,
  BeakerIcon,
  GlobeAltIcon,
  FolderIcon,
  AdjustmentsHorizontalIcon,
};

/**
 * Get icon component by name
 * @param {string} iconName - Name of the icon
 * @returns {React.Component} Icon component
 */
export const getIconByName = (iconName) => {
  return CATEGORY_ICONS[iconName] || SparklesIcon;
};

/**
 * Category color mappings for Tailwind CSS classes
 */
export const CATEGORY_COLORS = {
  purple: {
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    text: 'text-purple-700',
    hoverBg: 'hover:bg-purple-100',
    iconBg: 'bg-purple-100',
    iconText: 'text-purple-600',
    gradient: 'from-purple-50 to-purple-100',
    badge: 'bg-purple-100 text-purple-700',
  },
  blue: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-700',
    hoverBg: 'hover:bg-blue-100',
    iconBg: 'bg-blue-100',
    iconText: 'text-blue-600',
    gradient: 'from-blue-50 to-blue-100',
    badge: 'bg-blue-100 text-blue-700',
  },
  green: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-700',
    hoverBg: 'hover:bg-green-100',
    iconBg: 'bg-green-100',
    iconText: 'text-green-600',
    gradient: 'from-green-50 to-green-100',
    badge: 'bg-green-100 text-green-700',
  },
  orange: {
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    text: 'text-orange-700',
    hoverBg: 'hover:bg-orange-100',
    iconBg: 'bg-orange-100',
    iconText: 'text-orange-600',
    gradient: 'from-orange-50 to-orange-100',
    badge: 'bg-orange-100 text-orange-700',
  },
  red: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-700',
    hoverBg: 'hover:bg-red-100',
    iconBg: 'bg-red-100',
    iconText: 'text-red-600',
    gradient: 'from-red-50 to-red-100',
    badge: 'bg-red-100 text-red-700',
  },
  cyan: {
    bg: 'bg-cyan-50',
    border: 'border-cyan-200',
    text: 'text-cyan-700',
    hoverBg: 'hover:bg-cyan-100',
    iconBg: 'bg-cyan-100',
    iconText: 'text-cyan-600',
    gradient: 'from-cyan-50 to-cyan-100',
    badge: 'bg-cyan-100 text-cyan-700',
  },
  yellow: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    text: 'text-yellow-700',
    hoverBg: 'hover:bg-yellow-100',
    iconBg: 'bg-yellow-100',
    iconText: 'text-yellow-600',
    gradient: 'from-yellow-50 to-yellow-100',
    badge: 'bg-yellow-100 text-yellow-700',
  },
  pink: {
    bg: 'bg-pink-50',
    border: 'border-pink-200',
    text: 'text-pink-700',
    hoverBg: 'hover:bg-pink-100',
    iconBg: 'bg-pink-100',
    iconText: 'text-pink-600',
    gradient: 'from-pink-50 to-pink-100',
    badge: 'bg-pink-100 text-pink-700',
  },
};

/**
 * Get color classes by color name
 * @param {string} color - Color name
 * @returns {object} Object with Tailwind CSS color classes
 */
export const getColorClasses = (color) => {
  return CATEGORY_COLORS[color] || CATEGORY_COLORS.purple;
};

/**
 * Difficulty level mappings
 */
export const DIFFICULTY_LEVELS = {
  Beginner: {
    color: 'green',
    label: 'Beginner',
    icon: '●',
  },
  Intermediate: {
    color: 'yellow',
    label: 'Intermediate',
    icon: '●●',
  },
  Advanced: {
    color: 'red',
    label: 'Advanced',
    icon: '●●●',
  },
};

/**
 * Get difficulty badge classes
 * @param {string} difficulty - Difficulty level
 * @returns {object} Object with badge configuration
 */
export const getDifficultyBadge = (difficulty) => {
  return DIFFICULTY_LEVELS[difficulty] || DIFFICULTY_LEVELS.Beginner;
};
