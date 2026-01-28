/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors
        csoki: {
          red: '#E31837',
          dark: '#1a1a1a',
        },
        // Competitor brand colors
        brand: {
          csoki: '#E31837',
          russell: '#FF6B00',
          verizon: '#CD040B',
          victra: '#000000',
          tmobile: '#E20074',
          uscellular: '#00A3E0',
        }
      }
    },
  },
  plugins: [],
}
