/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'monospace'],
        sans: ['"IBM Plex Sans"', 'sans-serif'],
      },
      colors: {
        'ibm-blue':    'var(--ibm-blue-60)',
        'ibm-blue-lt': 'var(--ibm-blue-40)',
        'ibm-cyan':    'var(--ibm-cyan-30)',
        'ibm-teal':    'var(--ibm-teal-30)',
        'ibm-teal-dk': 'var(--ibm-teal-60)',
        'ibm-magenta': 'var(--ibm-magenta-40)',
        'ibm-purple':  'var(--ibm-purple-40)',
        surface:    'var(--bg-surface)',
        base:       'var(--bg-base)',
        nav:        'var(--bg-nav)',
        hero:       'var(--bg-hero)',
        'border-ui': 'var(--border-ui)',
        'text-1':   'var(--text-primary)',
        'text-2':   'var(--text-secondary)',
        'text-3':   'var(--text-tertiary)',
      },
    },
  },
  plugins: [],
}
