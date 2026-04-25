import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f7f6",
          100: "#e4e3e0",
          200: "#c8c6c0",
          300: "#a5a39b",
          400: "#82807a",
          500: "#64635e",
          600: "#4d4c48",
          700: "#3d3c39",
          800: "#2a2a28",
          900: "#1a1a19",
          950: "#0f0f0e",
        },
        accent: {
          DEFAULT: "#d4a574", // warm beige/bronze
          50: "#faf6f1",
          100: "#f4ead9",
          200: "#e7d2b2",
          300: "#d4a574",
          400: "#c28e50",
          500: "#a67238",
          600: "#865a2c",
          700: "#624222",
          800: "#3f2a17",
          900: "#1f150c",
        },
        signal: {
          success: "#6b8e5a",
          warning: "#c99e45",
          danger: "#b54a3c",
          info: "#5a7ea4",
        },
      },
      fontFamily: {
        display: ["Manrope", "-apple-system", "system-ui", "sans-serif"],
        sans: ["Manrope", "-apple-system", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
