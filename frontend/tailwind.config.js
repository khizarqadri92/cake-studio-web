/** Colours and fonts come from CSS variables that the admin-configured theme sets at runtime. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        secondary: "var(--color-secondary)",
        cream: "var(--color-background)",
        surface: "var(--color-surface)",
        ink: "var(--color-text)",
      },
      fontFamily: {
        heading: "var(--font-heading)",
        body: "var(--font-body)",
      },
      borderRadius: { btn: "var(--radius-btn)" },
      boxShadow: { card: "0 4px 24px -8px rgba(62,39,35,0.18)" },
    },
  },
  plugins: [],
};
