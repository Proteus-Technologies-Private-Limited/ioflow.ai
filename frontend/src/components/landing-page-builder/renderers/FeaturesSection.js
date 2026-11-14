import React from 'react';
import {
  BoltIcon,
  ShieldCheckIcon,
  GlobeAltIcon,
  ClockIcon,
  CpuChipIcon,
  LockClosedIcon,
  ChartBarIcon,
  CogIcon,
  StarIcon,
  HeartIcon,
  RocketLaunchIcon,
  CheckBadgeIcon,
} from '@heroicons/react/24/outline';

const ICON_MAP = {
  bolt: BoltIcon,
  'shield-check': ShieldCheckIcon,
  'globe-alt': GlobeAltIcon,
  clock: ClockIcon,
  'cpu-chip': CpuChipIcon,
  'lock-closed': LockClosedIcon,
  'chart-bar': ChartBarIcon,
  cog: CogIcon,
  star: StarIcon,
  heart: HeartIcon,
  'rocket-launch': RocketLaunchIcon,
  'check-badge': CheckBadgeIcon,
};

export const AVAILABLE_ICONS = Object.keys(ICON_MAP);

export default function FeaturesSection({ config }) {
  const items = config.items || [];
  const columns = config.columns || 3;

  if (items.length === 0) return null;

  return (
    <div className="py-8">
      {config.title && (
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">{config.title}</h2>
      )}
      <div
        className="grid gap-6"
        style={{ gridTemplateColumns: `repeat(${Math.min(columns, 4)}, minmax(0, 1fr))` }}
      >
        {items.map((item, idx) => {
          const IconComponent = ICON_MAP[item.icon] || StarIcon;
          return (
            <div
              key={idx}
              className="bg-white rounded-xl border border-gray-200 p-6 text-center hover:shadow-md transition-shadow"
            >
              <div className="inline-flex items-center justify-center w-12 h-12 bg-primary/10 rounded-lg mb-4">
                <IconComponent className="w-6 h-6 text-primary" />
              </div>
              {item.title && (
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{item.title}</h3>
              )}
              {item.description && (
                <p className="text-sm text-gray-600">{item.description}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
