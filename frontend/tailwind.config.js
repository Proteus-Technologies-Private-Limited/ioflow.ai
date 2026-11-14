/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // IOFlow Brand Colors - Reference CSS variables for centralized theming
        // These allow using Tailwind classes like `bg-brand-primary` or `text-brand-primary`
        brand: {
          // Primary cyan/teal
          primary: 'var(--color-primary)',
          'primary-light': 'var(--color-primary-light)',
          'primary-dark': 'var(--color-primary-dark)',
          'primary-darker': 'var(--color-primary-darker)',
          // Secondary teal/green
          secondary: 'var(--color-secondary)',
          'secondary-light': 'var(--color-secondary-light)',
          'secondary-dark': 'var(--color-secondary-dark)',
          'secondary-darker': 'var(--color-secondary-darker)',
          // Accent coral/orange (for CTAs)
          accent: 'var(--color-accent)',
          'accent-end': 'var(--color-accent-end)',
          'accent-hover': 'var(--color-accent-hover)',
          'accent-end-hover': 'var(--color-accent-end-hover)',
        },
        // Primary color scale using CSS variables
        primary: {
          DEFAULT: 'var(--color-primary)',
          light: 'var(--color-primary-light)',
          dark: 'var(--color-primary-dark)',
          darker: 'var(--color-primary-darker)',
          5: 'var(--color-primary-5)',
          10: 'var(--color-primary-10)',
          20: 'var(--color-primary-20)',
          30: 'var(--color-primary-30)',
          // Numeric scale for compatibility
          50: 'var(--color-primary-5)',
          100: 'var(--color-primary-10)',
          200: 'var(--color-primary-20)',
          300: 'var(--color-primary-30)',
          400: 'var(--color-primary-light)',
          500: 'var(--color-primary)',
          600: 'var(--color-primary-dark)',
          700: 'var(--color-primary-darker)',
          800: '#004055',
          900: '#00202b',
        },
        // Secondary color scale using CSS variables
        secondary: {
          DEFAULT: 'var(--color-secondary)',
          light: 'var(--color-secondary-light)',
          dark: 'var(--color-secondary-dark)',
          darker: 'var(--color-secondary-darker)',
          5: 'var(--color-secondary-5)',
          10: 'var(--color-secondary-10)',
          20: 'var(--color-secondary-20)',
          30: 'var(--color-secondary-30)',
          // Numeric scale for compatibility
          50: 'var(--color-secondary-5)',
          100: 'var(--color-secondary-10)',
          200: 'var(--color-secondary-20)',
          300: 'var(--color-secondary-30)',
          400: 'var(--color-secondary-light)',
          500: 'var(--color-secondary)',
          600: 'var(--color-secondary-dark)',
          700: 'var(--color-secondary-darker)',
          800: '#004840',
          900: '#002420',
        },
        // Accent colors using CSS variables
        accent: {
          DEFAULT: 'var(--color-accent)',
          end: 'var(--color-accent-end)',
          hover: 'var(--color-accent-hover)',
          'end-hover': 'var(--color-accent-end-hover)',
          10: 'var(--color-accent-10)',
          20: 'var(--color-accent-20)',
        },
      },
      backgroundColor: {
        // Additional background color utilities
        'theme-primary': 'var(--color-primary)',
        'theme-primary-10': 'var(--color-primary-10)',
        'theme-secondary': 'var(--color-secondary)',
        'theme-accent': 'var(--color-accent)',
      },
      textColor: {
        // Additional text color utilities
        'theme-primary': 'var(--color-primary)',
        'theme-primary-dark': 'var(--color-primary-dark)',
        'theme-secondary': 'var(--color-secondary)',
        'theme-accent': 'var(--color-accent)',
      },
      borderColor: {
        // Additional border color utilities
        'theme-primary': 'var(--color-primary)',
        'theme-primary-30': 'var(--color-primary-30)',
        'theme-secondary': 'var(--color-secondary)',
        'theme-accent': 'var(--color-accent)',
      },
      ringColor: {
        // Ring color utilities for focus states
        'theme-primary': 'var(--color-primary)',
        'theme-accent': 'var(--color-accent)',
      },
      backgroundImage: {
        // Brand gradients using CSS variables
        'gradient-primary': 'var(--gradient-primary)',
        'gradient-primary-vertical': 'var(--gradient-primary-vertical)',
        'gradient-accent': 'var(--gradient-accent)',
        'gradient-accent-hover': 'var(--gradient-accent-hover)',
        // Legacy gradient names for backward compatibility
        'brand-gradient': 'var(--gradient-primary)',
        'brand-gradient-vertical': 'var(--gradient-primary-vertical)',
        'accent-gradient': 'var(--gradient-accent)',
        'accent-gradient-hover': 'var(--gradient-accent-hover)',
      },
    },
  },
  plugins: [],
}
