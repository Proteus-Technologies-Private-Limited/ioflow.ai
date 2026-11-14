import { showErrorToast } from './customToast';

/**
 * Handle billing-related errors globally
 */
export const handleBillingError = (error) => {
  if (error.response?.status === 402) {
    const data = error.response.data;
    const requiredAmount = data.required_amount || 0;
    const availableAmount = data.available_amount || 0;
    const suggestedTopup = data.suggested_topup || 10;

    const errorMessage = `Insufficient balance. Required: $${requiredAmount.toFixed(2)}, Available: $${availableAmount.toFixed(2)}. Please top up at least $${suggestedTopup.toFixed(2)} to continue.`;

    showErrorToast(errorMessage);

    // Optionally show a modal or redirect to billing page
    if (data.billing_mode === 'PREPAID') {
      // Store error details in session storage for the billing page
      sessionStorage.setItem('billing_error', JSON.stringify({
        type: 'insufficient_balance',
        required: requiredAmount,
        available: availableAmount,
        suggested: suggestedTopup,
        message: data.message
      }));

      // Offer to redirect to billing page
      if (window.confirm('Insufficient balance. Would you like to go to the billing page to top up?')) {
        window.location.href = '/billing';
      }
    }

    return true; // Handled
  }

  return false; // Not handled
};

/**
 * Setup axios interceptor for billing errors
 */
export const setupBillingErrorInterceptor = (axios) => {
  axios.interceptors.response.use(
    response => response,
    error => {
      // Check if this is a billing error
      if (handleBillingError(error)) {
        // Still reject the promise so individual handlers can react
        return Promise.reject(error);
      }

      // Pass through other errors
      return Promise.reject(error);
    }
  );
};