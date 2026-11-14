import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const OnboardingContext = createContext({});

export const useOnboarding = () => {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within an OnboardingProvider');
  }
  return context;
};

export const OnboardingProvider = ({ children }) => {
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [onboardingStatus, setOnboardingStatus] = useState(null);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardDismissed, setWizardDismissed] = useState(false); // Track if user dismissed wizard
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [initialAppFilter, setInitialAppFilter] = useState(null); // For pre-selecting filter in ApplicationSetupStep

  // Fetch onboarding status from API
  const fetchOnboardingStatus = useCallback(async () => {
    // Wait for auth to finish loading
    if (authLoading) {
      return;
    }

    if (!isAuthenticated || !user) {
      setLoading(false);
      setShowWizard(false);
      return;
    }

    try {
      setLoading(true);
      const response = await axios.get('/api/v1/onboarding/status');
      setOnboardingStatus(response.data);
      setShowWizard(response.data.show_wizard);
      setError(null);

      // If wizard should show, determine which step to start with
      if (response.data.show_wizard && response.data.steps) {
        const steps = response.data.steps;
        // Find first incomplete and non-skipped step
        if (!steps.ai_configuration.completed && !steps.ai_configuration.skipped) {
          setCurrentStep(0);
        } else if (!steps.balance_topup.completed && !steps.balance_topup.skipped) {
          setCurrentStep(1);
        } else if (!steps.application_setup.completed && !steps.application_setup.skipped) {
          setCurrentStep(2);
        }
      }
    } catch (err) {
      console.error('Failed to fetch onboarding status:', err);
      setError(err.response?.data?.detail || 'Failed to fetch onboarding status');
      setShowWizard(false);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, user, authLoading]);

  // Fetch status on mount and when auth changes
  useEffect(() => {
    fetchOnboardingStatus();
  }, [fetchOnboardingStatus]);

  // Skip a specific step
  const skipStep = useCallback(async (stepId) => {
    try {
      await axios.post('/api/v1/onboarding/skip-step', { step_id: stepId });
      // Refresh status after skipping
      await fetchOnboardingStatus();
      return true;
    } catch (err) {
      console.error('Failed to skip step:', err);
      setError(err.response?.data?.detail || 'Failed to skip step');
      return false;
    }
  }, [fetchOnboardingStatus]);

  // Complete the entire wizard
  const completeWizard = useCallback(async () => {
    try {
      await axios.post('/api/v1/onboarding/complete');
      setShowWizard(false);
      await fetchOnboardingStatus();
      return true;
    } catch (err) {
      console.error('Failed to complete wizard:', err);
      setError(err.response?.data?.detail || 'Failed to complete wizard');
      return false;
    }
  }, [fetchOnboardingStatus]);

  // Refresh status (useful after external changes like configuring AI in Settings)
  const refreshStatus = useCallback(async () => {
    await fetchOnboardingStatus();
  }, [fetchOnboardingStatus]);

  // Temporarily dismiss wizard (will reappear on page refresh if steps not complete)
  const dismissWizard = useCallback(() => {
    setShowWizard(false);
    setWizardDismissed(true);
  }, []);

  // Resume the wizard after it was dismissed
  const resumeWizard = useCallback(async () => {
    // Refresh status first to pick up any changes made while wizard was dismissed
    try {
      const response = await axios.get('/api/v1/onboarding/status');
      setOnboardingStatus(response.data);

      // If there are still incomplete steps, show the wizard
      if (response.data.steps) {
        const steps = response.data.steps;
        // Find first incomplete and non-skipped step
        if (!steps.ai_configuration.completed && !steps.ai_configuration.skipped) {
          setCurrentStep(0);
        } else if (!steps.balance_topup.completed && !steps.balance_topup.skipped) {
          setCurrentStep(1);
        } else if (!steps.application_setup.completed && !steps.application_setup.skipped) {
          setCurrentStep(2);
        }
      }
    } catch (err) {
      console.error('Failed to refresh onboarding status:', err);
    }

    setShowWizard(true);
    setWizardDismissed(false);
  }, []);

  // Open the wizard manually (e.g., from dashboard) - works even after wizard was completed/skipped
  const openWizard = useCallback(async () => {
    // Refresh status first
    try {
      const response = await axios.get('/api/v1/onboarding/status');
      setOnboardingStatus(response.data);

      // Find first incomplete step (or start at beginning if all complete)
      if (response.data.steps) {
        const steps = response.data.steps;
        if (!steps.ai_configuration.completed) {
          setCurrentStep(0);
        } else if (!steps.balance_topup.completed) {
          setCurrentStep(1);
        } else if (!steps.application_setup.completed) {
          setCurrentStep(2);
        } else {
          // All complete, start at beginning
          setCurrentStep(0);
        }
      }
    } catch (err) {
      console.error('Failed to refresh onboarding status:', err);
    }

    setShowWizard(true);
    setWizardDismissed(false);
  }, []);

  // Open wizard with app setup step and pre-selected filter
  const openWizardWithAppFilter = useCallback(async (filterValue) => {
    // Refresh status first
    try {
      const response = await axios.get('/api/v1/onboarding/status');
      setOnboardingStatus(response.data);
    } catch (err) {
      console.error('Failed to refresh onboarding status:', err);
    }

    // Set the initial filter for ApplicationSetupStep
    setInitialAppFilter(filterValue);
    // Go directly to application setup step (index 2)
    setCurrentStep(2);
    setShowWizard(true);
    setWizardDismissed(false);
  }, []);

  // Clear the initial app filter (called after ApplicationSetupStep reads it)
  const clearInitialAppFilter = useCallback(() => {
    setInitialAppFilter(null);
  }, []);

  // Navigate to next step
  const nextStep = useCallback(() => {
    if (currentStep < 2) {
      setCurrentStep(currentStep + 1);
    }
  }, [currentStep]);

  // Navigate to previous step
  const prevStep = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  }, [currentStep]);

  // Go to a specific step
  const goToStep = useCallback((stepIndex) => {
    if (stepIndex >= 0 && stepIndex <= 2) {
      setCurrentStep(stepIndex);
    }
  }, []);

  // Check if setup is incomplete (at least one step not done and not skipped)
  const isSetupIncomplete = onboardingStatus?.show_wizard === true || (
    onboardingStatus?.steps && (
      (!onboardingStatus.steps.ai_configuration?.completed && !onboardingStatus.steps.ai_configuration?.skipped) ||
      (!onboardingStatus.steps.balance_topup?.completed && !onboardingStatus.steps.balance_topup?.skipped) ||
      (!onboardingStatus.steps.application_setup?.completed && !onboardingStatus.steps.application_setup?.skipped)
    )
  );

  // Can resume wizard if it was dismissed but setup is incomplete
  const canResumeWizard = wizardDismissed && isSetupIncomplete && !showWizard;

  // Check if user is an admin (TENANT_ADMIN or INSTANCE_ADMIN)
  const isAdmin = user?.role === 'TENANT_ADMIN' || user?.role === 'INSTANCE_ADMIN';

  // Check if any step has progress (something completed or skipped)
  const hasSetupProgress = onboardingStatus?.steps && (
    onboardingStatus.steps.ai_configuration?.completed ||
    onboardingStatus.steps.ai_configuration?.skipped ||
    onboardingStatus.steps.balance_topup?.completed ||
    onboardingStatus.steps.balance_topup?.skipped ||
    onboardingStatus.steps.application_setup?.completed ||
    onboardingStatus.steps.application_setup?.skipped
  );

  const value = {
    // State
    onboardingStatus,
    showWizard,
    wizardDismissed,
    currentStep,
    loading,
    error,
    isSetupIncomplete,
    canResumeWizard,
    isAdmin,
    hasSetupProgress,
    initialAppFilter,

    // Actions
    setShowWizard,
    setCurrentStep,
    skipStep,
    completeWizard,
    refreshStatus,
    dismissWizard,
    resumeWizard,
    openWizard,
    openWizardWithAppFilter,
    clearInitialAppFilter,
    nextStep,
    prevStep,
    goToStep
  };

  return (
    <OnboardingContext.Provider value={value}>
      {children}
    </OnboardingContext.Provider>
  );
};

export default OnboardingContext;
