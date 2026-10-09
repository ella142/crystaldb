import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1d2b3a",
        paper: "#f7f9fb",
        line: "#d9e2ea",
        blue: {
          50: "#eef6ff",
          100: "#dcecff",
          500: "#2474bb",
          600: "#165f9d",
          700: "#114d80",
        },
        teal: {
          50: "#effaf8",
          100: "#d8f2ed",
          600: "#117b6d",
          700: "#0d6157",
        },
        amber: {
          50: "#fff8e8",
          100: "#fcecc2",
          700: "#9a6a00",
        },
      },
      boxShadow: {
        panel: "0 14px 34px rgba(29, 43, 58, 0.07)",
        soft: "0 4px 16px rgba(29, 43, 58, 0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
