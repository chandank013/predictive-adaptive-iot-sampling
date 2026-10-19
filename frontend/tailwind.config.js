/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0d3b4f",
          800: "#124a63",
          700: "#1a5a76",
        },
        accent: {
          green: "#1a9b6c",
          red: "#d94b4b",
          blue: "#3366cc",
          orange: "#e08a2c",
          purple: "#6d5ce6",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
