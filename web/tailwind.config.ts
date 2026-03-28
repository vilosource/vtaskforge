import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // MD3 Primary
        'primary': '#004cc9',
        'primary-container': '#2865ed',
        'primary-fixed': '#dbe1ff',
        'primary-fixed-dim': '#b4c5ff',
        'on-primary': '#ffffff',
        'on-primary-fixed': '#00174b',
        'on-primary-fixed-variant': '#003ea8',
        'on-primary-container': '#f1f2ff',
        'inverse-primary': '#b4c5ff',

        // MD3 Secondary
        'secondary': '#505f76',
        'secondary-container': '#d0e1fb',
        'secondary-fixed': '#d3e4fe',
        'secondary-fixed-dim': '#b7c8e1',
        'on-secondary': '#ffffff',
        'on-secondary-fixed': '#0b1c30',
        'on-secondary-fixed-variant': '#38485d',
        'on-secondary-container': '#54647a',

        // MD3 Tertiary
        'tertiary': '#006443',
        'tertiary-container': '#007f57',
        'tertiary-fixed': '#6ffbbe',
        'tertiary-fixed-dim': '#4edea3',
        'on-tertiary': '#ffffff',
        'on-tertiary-fixed': '#002113',
        'on-tertiary-fixed-variant': '#005236',
        'on-tertiary-container': '#ccffe2',

        // MD3 Error
        'error': '#ba1a1a',
        'error-container': '#ffdad6',
        'on-error': '#ffffff',
        'on-error-container': '#93000a',

        // MD3 Surface
        'surface': '#f7f9fb',
        'surface-dim': '#d8dadc',
        'surface-bright': '#f7f9fb',
        'surface-variant': '#e0e3e5',
        'surface-tint': '#0053db',
        'surface-container-lowest': '#ffffff',
        'surface-container-low': '#f2f4f6',
        'surface-container': '#eceef0',
        'surface-container-high': '#e6e8ea',
        'surface-container-highest': '#e0e3e5',
        'on-surface': '#191c1e',
        'on-surface-variant': '#424656',
        'inverse-surface': '#2d3133',
        'inverse-on-surface': '#eff1f3',

        // MD3 Outline
        'outline': '#737687',
        'outline-variant': '#c2c6d9',

        // MD3 Background
        'background': '#f7f9fb',
        'on-background': '#191c1e',
      },
      fontFamily: {
        'headline': ['Manrope', 'sans-serif'],
        'body': ['Inter', 'sans-serif'],
        'label': ['Inter', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '0.125rem',
        lg: '0.25rem',
        xl: '0.5rem',
        full: '0.75rem',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
} satisfies Config;
