import React from 'react';
import { XMarkIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { useOnboarding } from '../../contexts/OnboardingContext';
import AIConfigurationStep from './steps/AIConfigurationStep';
import BalanceTopupStep from './steps/BalanceTopupStep';
import ApplicationSetupStep from './steps/ApplicationSetupStep';

const STEPS = [
  { id: 'ai_configuration', title: 'Configure AI Provider', component: AIConfigurationStep },
  { id: 'balance_topup', title: 'Top Up Balance', component: BalanceTopupStep },
  { id: 'application_setup', title: 'Connect Applications', component: ApplicationSetupStep },
];

const AdminOnboardingWizard = () => {
  const {
    onboardingStatus,
    currentStep,
    setCurrentStep,
    skipStep,
    completeWizard,
    dismissWizard,
    refreshStatus,
  } = useOnboarding();

  if (!onboardingStatus?.steps) {
    return null;
  }

  const steps = onboardingStatus.steps;
  const currentStepConfig = STEPS[currentStep];
  const CurrentStepComponent = currentStepConfig?.component;

  // Check if current step is already complete
  const isCurrentStepComplete = steps[currentStepConfig.id]?.completed;
  const isCurrentStepSkipped = steps[currentStepConfig.id]?.skipped;

  // Check if all steps are done (completed or skipped)
  const allStepsDone = STEPS.every(
    (step) => steps[step.id]?.completed || steps[step.id]?.skipped
  );

  const handleSkip = async () => {
    await skipStep(currentStepConfig.id);
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleComplete = async () => {
    await completeWizard();
  };

  const getStepStatus = (stepIndex) => {
    const step = STEPS[stepIndex];
    const stepData = steps[step.id];
    if (stepData?.completed) return 'completed';
    if (stepData?.skipped) return 'skipped';
    if (stepIndex === currentStep) return 'current';
    return 'pending';
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-3xl transform overflow-hidden rounded-2xl bg-white shadow-xl transition-all">
          {/* Close button */}
          <button
            onClick={dismissWizard}
            className="absolute right-4 top-4 text-gray-400 hover:text-gray-500 z-10"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>

          {/* Header */}
          <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
            <h2 className="text-xl font-semibold text-gray-900">
              Welcome to IOFlow
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Let's get you set up in just a few steps
            </p>
          </div>

          {/* Progress bar */}
          <div className="px-6 py-4 border-b border-gray-100">
            <div className="flex items-center justify-between">
              {STEPS.map((step, index) => (
                <React.Fragment key={step.id}>
                  {/* Step indicator */}
                  <button
                    onClick={() => setCurrentStep(index)}
                    className="flex flex-col items-center flex-1"
                  >
                    <div
                      className={`
                        w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium
                        transition-colors duration-200
                        ${getStepStatus(index) === 'completed'
                          ? 'bg-green-500 text-white'
                          : getStepStatus(index) === 'skipped'
                          ? 'bg-gray-300 text-gray-600'
                          : getStepStatus(index) === 'current'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-500'
                        }
                      `}
                    >
                      {getStepStatus(index) === 'completed' ? (
                        <CheckCircleIcon className="h-6 w-6" />
                      ) : (
                        index + 1
                      )}
                    </div>
                    <span
                      className={`
                        mt-2 text-xs font-medium
                        ${getStepStatus(index) === 'current'
                          ? 'text-blue-600'
                          : getStepStatus(index) === 'completed'
                          ? 'text-green-600'
                          : 'text-gray-500'
                        }
                      `}
                    >
                      {step.title}
                    </span>
                  </button>

                  {/* Connector line */}
                  {index < STEPS.length - 1 && (
                    <div
                      className={`
                        h-0.5 flex-1 mx-2
                        ${steps[STEPS[index].id]?.completed || steps[STEPS[index].id]?.skipped
                          ? 'bg-green-500'
                          : 'bg-gray-200'
                        }
                      `}
                    />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Step content */}
          <div className="px-6 py-6 min-h-[400px] max-h-[60vh] overflow-y-auto">
            {CurrentStepComponent && (
              <CurrentStepComponent
                stepData={steps[currentStepConfig.id]}
                onComplete={refreshStatus}
              />
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-200 bg-gray-50 px-6 py-4">
            <div className="flex items-center justify-between">
              {/* Skip button */}
              <button
                onClick={handleSkip}
                disabled={isCurrentStepComplete || isCurrentStepSkipped}
                className={`
                  px-4 py-2 text-sm font-medium rounded-lg
                  ${isCurrentStepComplete || isCurrentStepSkipped
                    ? 'text-gray-400 cursor-not-allowed'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                  }
                `}
              >
                Skip this step
              </button>

              <div className="flex items-center space-x-3">
                {/* Previous button */}
                {currentStep > 0 && (
                  <button
                    onClick={handlePrevious}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    Previous
                  </button>
                )}

                {/* Next/Complete button */}
                {currentStep < STEPS.length - 1 ? (
                  <button
                    onClick={handleNext}
                    className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                  >
                    Next
                  </button>
                ) : (
                  <button
                    onClick={handleComplete}
                    disabled={!allStepsDone && !isCurrentStepComplete && !isCurrentStepSkipped}
                    className={`
                      px-6 py-2 text-sm font-medium rounded-lg
                      ${allStepsDone || isCurrentStepComplete || isCurrentStepSkipped
                        ? 'text-white bg-green-600 hover:bg-green-700'
                        : 'text-gray-400 bg-gray-200 cursor-not-allowed'
                      }
                    `}
                  >
                    Complete Setup
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminOnboardingWizard;
