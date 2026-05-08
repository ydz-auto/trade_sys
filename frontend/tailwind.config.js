/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#F59E0B',
        secondary: '#FBBF24',
        accent: '#8B5CF6',
        background: '#0F172A',
        surface: '#1E293B',
        border: '#334155',
        'text-primary': '#F8FAFC',
        'text-secondary': '#94A3B8',
        bullish: '#10B981',
        bearish: '#EF4444',
        warning: '#F97316',
        neutral: '#3B82F6',
      },
      fontFamily: {
        heading: ['Fira Code', 'monospace'],
        body: ['Fira Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
