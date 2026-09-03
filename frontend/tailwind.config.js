/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Semantic Surfaces & Borders from TMATH_DESIGN_SYSTEM
        app: "var(--bg-app)",
        sidebar: "var(--bg-sidebar)",
        card: {
          DEFAULT: "var(--bg-card)",
          hover: "var(--bg-card-hover)",
          subtle: "var(--bg-subtle)",
        },
        border: {
          DEFAULT: "var(--border-subtle)",
          subtle: "var(--border-subtle)",
          strong: "var(--border-strong)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          disabled: "var(--text-disabled)",
        },

        // Verdict competitive programming colors
        verdict: {
          ac: "var(--verdict-ac)",
          wa: "var(--verdict-wa)",
          tle: "var(--verdict-tle)",
          rte: "var(--verdict-rte)",
          ce: "var(--verdict-ce)",
        },

        // Bloom taxonomy scale
        bloom: {
          a: "var(--bloom-a)",
          b: "var(--bloom-b)",
          c: "var(--bloom-c)",
          d: "var(--bloom-d)",
          e: "var(--bloom-e)",
          f: "var(--bloom-f)",
        },

        // Brand accents
        brand: {
          primary: "var(--brand-primary)",
          hover: "var(--brand-primary-hover)",
          cyan: "var(--brand-cyan)",
          // Backward compatibility mappings
          blue: "#3B82F6",
          purple: "#8B5CF6",
          emerald: "#10B981",
          amber: "#F59E0B",
          rose: "#F43F5E"
        },

        // Backward compatibility mappings for legacy classes
        dark: {
          bg: "var(--bg-app)",
          card: "var(--bg-card)",
          border: "var(--border-subtle)",
          hover: "var(--border-strong)"
        }
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        // Elevation mức 1: card trên canvas, đủ phân tầng mà không nổi bồng bềnh
        xs: "0 1px 2px 0 rgba(15, 23, 42, 0.05)",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "SF Mono", "Consolas", "monospace"],
      }
    },
  },
  plugins: [],
}
