/** @type {import("tailwindcss").Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      backgroundOpacity: { 3: "0.03", 8: "0.08" },
    },
  },
  plugins: [],
};