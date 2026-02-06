/**
 * Shared formatting utilities for numbers, currency, and compact display.
 */

/** Format number with commas (e.g., 1,234,567) */
export const formatNumber = (num: number | null | undefined): string => {
  if (num === null || num === undefined) return 'N/A';
  return num.toLocaleString();
};

/** Format as currency (e.g., $1,234,567) */
export const formatCurrency = (num: number | null | undefined): string => {
  if (num === null || num === undefined) return 'N/A';
  return '$' + num.toLocaleString();
};

/** Format as compact currency (e.g., $1.2M, $45K) */
export const formatCurrencyCompact = (num: number | null | undefined): string => {
  if (num === null || num === undefined) return 'N/A';
  if (num >= 1000000) return '$' + (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return '$' + (num / 1000).toFixed(0) + 'K';
  return '$' + num.toLocaleString();
};

/** Format as compact number (e.g., 1.2M, 45.3K) */
export const formatCompact = (num: number | null | undefined): string => {
  if (num === null || num === undefined) return 'N/A';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
};

/** Format as Intl currency (e.g., $1,234,567 with proper locale formatting) */
export const formatCurrencyIntl = (value: number | null | undefined): string => {
  if (!value) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};
