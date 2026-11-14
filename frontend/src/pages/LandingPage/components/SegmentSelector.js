/**
 * SegmentSelector - Tab-based segment switcher for the landing page
 */

import React from 'react';
import { Building2, Rocket, Briefcase } from 'lucide-react';

const segments = [
  {
    id: 'enterprise',
    label: 'Enterprise & ISV',
    shortLabel: 'Enterprise',
    icon: Building2,
    description: 'Build integrations for any system'
  },
  {
    id: 'developers',
    label: 'No-Code Developers',
    shortLabel: 'Developers',
    icon: Rocket,
    description: 'Create and monetize Micro SaaS apps'
  },
  {
    id: 'business',
    label: 'Business Users',
    shortLabel: 'Business',
    icon: Briefcase,
    description: 'Automate your daily tasks'
  }
];

const SegmentSelector = ({ activeSegment, onSegmentChange }) => {
  return (
    <div className="flex flex-col items-center">
      <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2 text-center">
        Choose Your Path
      </h2>
      <p className="text-gray-600 mb-8 text-center max-w-2xl">
        Whether you're building enterprise integrations, creating Micro SaaS products, or automating business tasks - IOFlow has you covered.
      </p>

      {/* Tab Buttons */}
      <div className="flex flex-col sm:flex-row gap-3 w-full max-w-4xl">
        {segments.map(segment => {
          const Icon = segment.icon;
          const isActive = activeSegment === segment.id;

          return (
            <button
              key={segment.id}
              onClick={() => onSegmentChange(segment.id)}
              className={`
                flex-1 flex flex-col items-center gap-2 p-4 md:p-6 rounded-xl
                border-2 transition-all duration-300
                ${isActive
                  ? 'border-primary bg-gradient-to-br from-primary/10 to-secondary/10 shadow-lg'
                  : 'border-gray-200 bg-white hover:border-primary/50 hover:shadow-md'}
              `}
            >
              <div className={`
                p-3 rounded-full transition-colors
                ${isActive ? 'bg-gradient-to-br from-primary to-secondary text-white' : 'bg-gray-100 text-gray-600'}
              `}>
                <Icon className="w-6 h-6" />
              </div>
              <span className={`
                font-semibold text-lg transition-colors
                ${isActive ? 'text-primary' : 'text-gray-900'}
              `}>
                <span className="hidden md:inline">{segment.label}</span>
                <span className="md:hidden">{segment.shortLabel}</span>
              </span>
              <span className="text-sm text-gray-500 hidden md:block text-center">
                {segment.description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default SegmentSelector;
