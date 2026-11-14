/**
 * DemoWalkthrough - Interactive demo container with step-by-step walkthrough
 */

import React, { useState, useEffect } from 'react';
import DemoStep from './DemoStep';
import MockFlowVisualization from './MockFlowVisualization';
import { Play, Pause, RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react';

const DemoWalkthrough = ({ demo, isOpen, onClose, onAction }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [completedSteps, setCompletedSteps] = useState([]);

  const steps = demo?.steps || [];
  const totalSteps = steps.length;

  // Auto-play through steps
  useEffect(() => {
    if (!isPlaying || currentStep >= totalSteps - 1) return;

    const timer = setTimeout(() => {
      handleNextStep();
    }, 3000);

    return () => clearTimeout(timer);
  }, [isPlaying, currentStep, totalSteps]);

  // Reset when demo changes
  useEffect(() => {
    setCurrentStep(0);
    setCompletedSteps([]);
    setIsPlaying(false);
  }, [demo]);

  const handleNextStep = () => {
    if (currentStep < totalSteps - 1) {
      setCompletedSteps(prev => [...prev, currentStep]);
      setCurrentStep(prev => prev + 1);
    } else {
      setIsPlaying(false);
    }
  };

  const handlePrevStep = () => {
    if (currentStep > 0) {
      setCompletedSteps(prev => prev.filter(s => s !== currentStep - 1));
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleStepClick = (index) => {
    setCurrentStep(index);
    setCompletedSteps(Array.from({ length: index }, (_, i) => i));
  };

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setCurrentStep(0);
    setCompletedSteps([]);
    setIsPlaying(false);
  };

  const handleTryIt = () => {
    onAction?.('try-demo', { demo: demo.title, step: currentStep });
  };

  if (!demo) return null;

  return (
    <div className="bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-primary px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold text-white">{demo.title}</h3>
            <p className="text-white/80 text-sm">{demo.description}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
              title="Reset demo"
            >
              <RotateCcw className="w-5 h-5 text-white" />
            </button>
            <button
              onClick={handlePlayPause}
              className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? (
                <Pause className="w-5 h-5 text-white" />
              ) : (
                <Play className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-4 flex items-center gap-2">
          {steps.map((_, index) => (
            <button
              key={index}
              onClick={() => handleStepClick(index)}
              className={`
                flex-1 h-2 rounded-full transition-all duration-300 cursor-pointer
                ${index === currentStep
                  ? 'bg-white'
                  : completedSteps.includes(index)
                    ? 'bg-white/60'
                    : 'bg-white/20 hover:bg-white/30'}
              `}
            />
          ))}
        </div>
        <div className="mt-2 text-white/80 text-sm text-center">
          Step {currentStep + 1} of {totalSteps}
        </div>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
        {/* Left: Step Details */}
        <div className="p-6 border-r border-gray-200">
          <DemoStep
            step={steps[currentStep]}
            isActive={true}
            stepNumber={currentStep + 1}
          />

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pt-4 border-t border-gray-200">
            <button
              onClick={handlePrevStep}
              disabled={currentStep === 0}
              className="flex items-center gap-1 px-4 py-2 text-gray-600 hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-5 h-5" />
              Previous
            </button>

            {currentStep === totalSteps - 1 ? (
              <button
                onClick={handleTryIt}
                className="px-6 py-2 bg-gradient-accent text-white font-medium rounded-lg hover:from-[#dc6b7e] hover:to-[#e8915c] transition-colors"
              >
                Try It Yourself
              </button>
            ) : (
              <button
                onClick={handleNextStep}
                className="flex items-center gap-1 px-4 py-2 text-primary hover:text-primary-dark font-medium transition-colors"
              >
                Next
                <ChevronRight className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {/* Right: Flow Visualization */}
        <div className="bg-gray-50 p-6">
          <MockFlowVisualization
            steps={steps}
            currentStep={currentStep}
            completedSteps={completedSteps}
          />
        </div>
      </div>
    </div>
  );
};

export default DemoWalkthrough;
