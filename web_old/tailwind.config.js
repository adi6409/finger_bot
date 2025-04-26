import colors from 'tailwindcss/colors'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    colors: {
      gray: colors.gray,
      blue: colors.blue,
      red: colors.red,
      green: colors.green,
      // Add other colors as needed
    },
    extend: {},
  },
  plugins: [],
}
