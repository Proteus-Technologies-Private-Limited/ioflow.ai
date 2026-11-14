/**
 * SignupPrompt - Modal overlay prompting users to sign up
 * Appears when users try to interact with demos or subscribe to apps
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Zap, ArrowRight, Play, CheckCircle } from 'lucide-react';

const SignupPrompt = ({ context, onClose }) => {
  const navigate = useNavigate();

  const handleSignUp = () => {
    navigate('/register');
    onClose();
  };

  const handleSignIn = () => {
    navigate('/login');
    onClose();
  };

  const handleContinueBrowsing = () => {
    onClose();
  };

  // Determine prompt content based on context
  const getPromptContent = () => {
    switch (context?.action) {
      case 'try-demo':
        return {
          title: 'Ready to Try It Yourself?',
          description: 'Create a free account to build your own workflows and experience the full power of IOFlow.',
          icon: Play,
          benefits: [
            'Build unlimited flows in sandbox mode',
            'Access all integrations',
            'No credit card required'
          ]
        };
      case 'subscribe':
        return {
          title: 'Subscribe to This App',
          description: 'Sign up to subscribe and start using this automation right away.',
          icon: CheckCircle,
          benefits: [
            'Instant access after signup',
            'Many free apps available',
            'Cancel anytime'
          ]
        };
      default:
        return {
          title: 'Get Started with IOFlow',
          description: 'Create your free account and start automating your workflows today.',
          icon: Zap,
          benefits: [
            '5 free flows per month',
            'Access to marketplace',
            'Community support'
          ]
        };
    }
  };

  const content = getPromptContent();
  const Icon = content.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-scale-in">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors z-10"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="bg-gradient-primary px-6 py-8 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/20 mb-4">
            <Icon className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">
            {content.title}
          </h2>
          <p className="text-white/80">
            {content.description}
          </p>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          {/* Benefits */}
          <ul className="space-y-3 mb-6">
            {content.benefits.map((benefit, index) => (
              <li key={index} className="flex items-center gap-3">
                <CheckCircle className="w-5 h-5 text-primary flex-shrink-0" />
                <span className="text-gray-700">{benefit}</span>
              </li>
            ))}
          </ul>

          {/* CTA Buttons */}
          <div className="space-y-3">
            <button
              onClick={handleSignUp}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-gradient-accent text-white font-semibold rounded-lg hover:from-[#dc6b7e] hover:to-[#e8915c] transition-colors shadow-lg"
            >
              Create Free Account
              <ArrowRight className="w-5 h-5" />
            </button>

            <button
              onClick={handleSignIn}
              className="w-full px-6 py-3 text-primary font-medium rounded-lg hover:bg-primary-10 transition-colors"
            >
              Already have an account? Sign In
            </button>
          </div>

          {/* Continue browsing */}
          <div className="mt-6 text-center">
            <button
              onClick={handleContinueBrowsing}
              className="text-gray-500 hover:text-gray-700 text-sm transition-colors"
            >
              Continue browsing
            </button>
          </div>
        </div>
      </div>

      {/* CSS for animation */}
      <style jsx>{`
        @keyframes scale-in {
          0% {
            opacity: 0;
            transform: scale(0.95);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }
        .animate-scale-in {
          animation: scale-in 0.2s ease-out;
        }
      `}</style>
    </div>
  );
};

export default SignupPrompt;
