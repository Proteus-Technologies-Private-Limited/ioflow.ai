/**
 * Currency helpers for Micro SaaS billing.
 *
 * A single source of truth for the supported currencies and their symbols so
 * Billing Configuration, Revenue Metrics, Billing History, Transactions and
 * Analytics all render amounts consistently.
 */

export const SUPPORTED_CURRENCIES = [
  { code: 'USD', symbol: '$', label: 'USD ($)' },
  { code: 'EUR', symbol: '€', label: 'EUR (€)' },
  { code: 'GBP', symbol: '£', label: 'GBP (£)' },
  { code: 'INR', symbol: '₹', label: 'INR (₹)' },
  { code: 'AUD', symbol: 'A$', label: 'AUD (A$)' },
  { code: 'CAD', symbol: 'C$', label: 'CAD (C$)' },
];

const SYMBOL_BY_CODE = SUPPORTED_CURRENCIES.reduce((acc, c) => {
  acc[c.code] = c.symbol;
  return acc;
}, {});

export const DEFAULT_CURRENCY = 'USD';

/**
 * Resolve the symbol for a currency code, falling back to the code itself
 * (so an unknown/legacy code is still shown, never blank).
 */
export const getCurrencySymbol = (code) => {
  if (!code) return SYMBOL_BY_CODE[DEFAULT_CURRENCY];
  return SYMBOL_BY_CODE[code] || `${code} `;
};

/**
 * Format a numeric amount with its currency symbol, e.g. formatCurrency(12.5, 'EUR') => "€12.50".
 */
export const formatCurrency = (amount, code = DEFAULT_CURRENCY, fractionDigits = 2) => {
  const value = Number.isFinite(amount) ? amount : 0;
  return `${getCurrencySymbol(code)}${value.toFixed(fractionDigits)}`;
};
