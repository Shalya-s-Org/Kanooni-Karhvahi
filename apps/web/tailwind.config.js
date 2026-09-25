/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        legal: {
          50: '#f8fafc',
          100: '#f1f5f9',
          500: '#1e3a8a',
          600: '#1e40af',
          700: '#1d4ed8',
          800: '#1e293b',
          900: '#0f172a',
        },
        india: {
          saffron: '#ff9933',
          navy: '#000080',
          green: '#138808'
        }
      }
    },
  },
  plugins: [],
}
