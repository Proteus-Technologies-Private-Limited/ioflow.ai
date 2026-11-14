/**
 * MockFlowVisualization - Animated mock flow diagram for demos
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
  Download,
  ArrowDown
} from 'lucide-react';

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

const nodeColors = {
  trigger: { bg: 'bg-blue-500', border: 'border-blue-600', glow: 'shadow-blue-200' },
  ai: { bg: 'bg-purple-500', border: 'border-purple-600', glow: 'shadow-purple-200' },
  database: { bg: 'bg-green-500', border: 'border-green-600', glow: 'shadow-green-200' },
  action: { bg: 'bg-orange-500', border: 'border-orange-600', glow: 'shadow-orange-200' },
  result: { bg: 'bg-emerald-500', border: 'border-emerald-600', glow: 'shadow-emerald-200' },
  design: { bg: 'bg-indigo-500', border: 'border-indigo-600', glow: 'shadow-indigo-200' },
  form: { bg: 'bg-cyan-500', border: 'border-cyan-600', glow: 'shadow-cyan-200' },
  pricing: { bg: 'bg-amber-500', border: 'border-amber-600', glow: 'shadow-amber-200' },
  publish: { bg: 'bg-rose-500', border: 'border-rose-600', glow: 'shadow-rose-200' },
  analytics: { bg: 'bg-teal-500', border: 'border-teal-600', glow: 'shadow-teal-200' },
  browse: { bg: 'bg-sky-500', border: 'border-sky-600', glow: 'shadow-sky-200' },
  subscribe: { bg: 'bg-lime-500', border: 'border-lime-600', glow: 'shadow-lime-200' },
  upload: { bg: 'bg-violet-500', border: 'border-violet-600', glow: 'shadow-violet-200' },
  extract: { bg: 'bg-pink-500', border: 'border-pink-600', glow: 'shadow-pink-200' },
  export: { bg: 'bg-emerald-500', border: 'border-emerald-600', glow: 'shadow-emerald-200' }
};

const MockFlowVisualization = ({ steps, currentStep, completedSteps }) => {
  return (
    <div className="relative h-full min-h-[400px] flex flex-col items-center justify-center py-4">
      {/* Flow Nodes */}
      <div className="flex flex-col items-center gap-2">
        {steps.map((step, index) => {
          const Icon = iconMap[step.icon] || CheckCircle;
          const colors = nodeColors[step.nodeType] || nodeColors.action;
          const isActive = index === currentStep;
          const isCompleted = completedSteps.includes(index);
          const isPending = index > currentStep;

          return (
            <React.Fragment key={step.id}>
              {/* Node */}
              <div
                className={`
                  relative flex items-center gap-3 px-4 py-3 rounded-xl
                  border-2 transition-all duration-500
                  ${isActive
                    ? `${colors.bg} ${colors.border} text-white shadow-lg ${colors.glow} scale-105`
                    : isCompleted
                      ? `bg-white ${colors.border} text-gray-700 opacity-80`
                      : 'bg-gray-100 border-gray-200 text-gray-400'}
                `}
              >
                {/* Pulse animation for active node */}
                {isActive && (
                  <div className={`absolute inset-0 ${colors.bg} rounded-xl animate-ping opacity-20`} />
                )}

                {/* Icon */}
                <div className={`
                  relative z-10 w-10 h-10 rounded-lg flex items-center justify-center
                  ${isActive
                    ? 'bg-white/20'
                    : isCompleted
                      ? colors.bg + ' text-white'
                      : 'bg-gray-200'}
                `}>
                  <Icon className="w-5 h-5" />
                </div>

                {/* Label */}
                <div className="relative z-10">
                  <div className={`font-medium text-sm ${isActive ? 'text-white' : ''}`}>
                    {step.title}
                  </div>
                  {isCompleted && (
                    <div className="text-xs text-green-600 flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" />
                      Completed
                    </div>
                  )}
                </div>

                {/* Step number badge */}
                <div className={`
                  absolute -left-3 -top-3 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                  ${isActive
                    ? 'bg-white text-indigo-600'
                    : isCompleted
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-300 text-gray-600'}
                `}>
                  {isCompleted ? '✓' : index + 1}
                </div>
              </div>

              {/* Connector Arrow */}
              {index < steps.length - 1 && (
                <div className={`
                  flex flex-col items-center transition-all duration-300
                  ${isCompleted ? 'text-green-400' : isPending ? 'text-gray-200' : 'text-indigo-400'}
                `}>
                  <div className={`
                    w-0.5 h-4 transition-colors duration-300
                    ${isCompleted ? 'bg-green-400' : isPending ? 'bg-gray-200' : 'bg-indigo-400'}
                  `} />
                  <ArrowDown className="w-4 h-4" />
                  <div className={`
                    w-0.5 h-4 transition-colors duration-300
                    ${isCompleted ? 'bg-green-400' : isPending ? 'bg-gray-200' : 'bg-indigo-400'}
                  `} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Animated particles (data flow effect) */}
      {currentStep > 0 && currentStep < steps.length && (
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute left-1/2 top-0 w-2 h-2 bg-indigo-400 rounded-full animate-flow-down opacity-60" />
          <div className="absolute left-1/2 top-0 w-2 h-2 bg-purple-400 rounded-full animate-flow-down opacity-60 animation-delay-500" />
        </div>
      )}

      {/* CSS for animations */}
      <style>{`
        @keyframes flow-down {
          0% {
            transform: translateY(0) translateX(-50%);
            opacity: 0;
          }
          10% {
            opacity: 0.6;
          }
          90% {
            opacity: 0.6;
          }
          100% {
            transform: translateY(400px) translateX(-50%);
            opacity: 0;
          }
        }
        .animate-flow-down {
          animation: flow-down 2s ease-in-out infinite;
        }
        .animation-delay-500 {
          animation-delay: 0.5s;
        }
      `}</style>
    </div>
  );
};

export default MockFlowVisualization;
