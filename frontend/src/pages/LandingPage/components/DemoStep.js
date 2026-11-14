/**
 * DemoStep - Single step display within the demo walkthrough
 */

import React from 'react';
import {
  Webhook,
  Brain,
  Database,
  Mail,
  CheckCircle,
  Workflow,
  FormInput,
  DollarSign,
  Rocket,
  TrendingUp,
  Search,
  Upload,
  FileSpreadsheet,
  Download
} from 'lucide-react';

// Icon mapping for demo steps
const iconMap = {
  Webhook,
  Brain,
  Database,
  Mail,
  CheckCircle,
  Workflow,
  FormInput,
  DollarSign,
  Rocket,
  TrendingUp,
  Search,
  Upload,
  FileSpreadsheet,
  Download
};

const DemoStep = ({ step, isActive, stepNumber }) => {
  if (!step) return null;

  const Icon = iconMap[step.icon] || CheckCircle;

  return (
    <div className={`transition-all duration-500 ${isActive ? 'opacity-100' : 'opacity-50'}`}>
      {/* Step Header */}
      <div className="flex items-start gap-4 mb-6">
        <div className={`
          flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center
          transition-all duration-500
          ${isActive
            ? 'bg-gradient-to-br from-primary to-secondary text-white shadow-lg shadow-primary/30'
            : 'bg-gray-100 text-gray-400'}
        `}>
          <Icon className="w-6 h-6" />
        </div>
        <div>
          <div className="text-sm text-primary font-medium mb-1">
            Step {stepNumber}
          </div>
          <h4 className="text-xl font-semibold text-gray-900">
            {step.title}
          </h4>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 mb-6 leading-relaxed">
        {step.description}
      </p>

      {/* Mock Data Display */}
      {step.mockData && (
        <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm overflow-x-auto">
          <div className="text-gray-400 mb-2 text-xs uppercase tracking-wide">
            Preview
          </div>
          {Object.entries(step.mockData).map(([key, value]) => (
            <div key={key} className="flex gap-2 mb-1 last:mb-0">
              <span className="text-purple-400">{key}:</span>
              <span className="text-green-400">
                {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DemoStep;
