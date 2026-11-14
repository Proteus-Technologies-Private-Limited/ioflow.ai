import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  SparklesIcon,
  CheckCircleIcon,
  ArrowTopRightOnSquareIcon,
  CpuChipIcon,
  CodeBracketIcon,
  LightBulbIcon,
} from '@heroicons/react/24/outline';
import { useOnboarding } from '../../../contexts/OnboardingContext';

const AIConfigurationStep = ({ stepData, onComplete }) => {
  const navigate = useNavigate();
  const { dismissWizard } = useOnboarding();

  const isCompleted = stepData?.completed;

  const handleConfigureNow = () => {
    // Temporarily dismiss wizard and navigate to AI Settings tab
    dismissWizard();
    navigate('/settings?tab=2');
  };

  const features = [
    {
      icon: SparklesIcon,
      title: 'AI-Assisted Flow Creation',
      description: 'Describe what you want and let AI build the flow for you',
    },
    {
      icon: CodeBracketIcon,
      title: 'Intelligent Transformations',
      description: 'Generate data transformation code automatically',
    },
    {
      icon: LightBulbIcon,
      title: 'Smart Suggestions',
      description: 'Get contextual suggestions as you design flows',
    },
  ];

  const providers = [
    { name: 'OpenAI', models: 'GPT-4, GPT-4o, o3' },
    { name: 'Anthropic', models: 'Claude 3.5, Claude 4' },
    { name: 'Google', models: 'Gemini Pro, Gemini Flash' },
    { name: 'Azure OpenAI', models: 'Custom deployments' },
    { name: 'DeepSeek', models: 'DeepSeek Chat, R1' },
    { name: 'Local', models: 'LM Studio, Ollama' },
  ];

  return (
    <div className="space-y-6">
      {/* Status banner */}
      {isCompleted ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
          <CheckCircleIcon className="h-6 w-6 text-green-600" />
          <div>
            <h3 className="text-sm font-medium text-green-800">AI Configuration Complete</h3>
            <p className="text-sm text-green-700">
              Your AI provider is configured and ready to use.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <CpuChipIcon className="h-6 w-6 text-blue-600 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-blue-800">Why Configure AI?</h3>
              <p className="text-sm text-blue-700 mt-1">
                Configuring an AI provider unlocks powerful features that help you build flows faster
                and write better transformations.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Features */}
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-3">AI-Powered Features</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {features.map((feature, index) => (
            <div
              key={index}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
            >
              <feature.icon className="h-8 w-8 text-blue-600 mb-2" />
              <h4 className="text-sm font-medium text-gray-900">{feature.title}</h4>
              <p className="text-xs text-gray-600 mt-1">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Supported Providers */}
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-3">Supported AI Providers</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {providers.map((provider, index) => (
            <div
              key={index}
              className="bg-gray-50 border border-gray-200 rounded-lg p-3"
            >
              <h4 className="text-sm font-medium text-gray-900">{provider.name}</h4>
              <p className="text-xs text-gray-500 mt-0.5">{provider.models}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Action */}
      {!isCompleted && (
        <div className="pt-4 border-t border-gray-200">
          <button
            onClick={handleConfigureNow}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Configure AI Provider
            <ArrowTopRightOnSquareIcon className="h-4 w-4" />
          </button>
          <p className="text-xs text-gray-500 mt-2">
            You'll be taken to Settings. After configuring, click the <strong>"Resume Setup"</strong> button to continue.
          </p>
        </div>
      )}
    </div>
  );
};

export default AIConfigurationStep;
