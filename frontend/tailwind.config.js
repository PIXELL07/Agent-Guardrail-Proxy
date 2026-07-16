/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B1014",
        panel: "#131A1F",
        panel2: "#171F25",
        border: "#232D34",
        muted: "#7E8C94",
        ink: "#E7EDF0",
        allow: "#2FD6B3",
        block: "#FF5C5C",
        judge: "#F2B84B",
        accent: "#4FA8FF",
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
