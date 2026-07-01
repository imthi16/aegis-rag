/** @type {import('tailwindcss').Config} */
// Aegis RAG — "Sovereign Instrument" theme.
// Color is earned: saturated hues appear only where they encode meaning
// (classification + trust). Everything else is ink and graphite. Monospace
// is the structural/display voice — the product's own material (hashes, ids,
// scores) is its typographic identity. No webfonts (zero-egress): system stacks.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Ink base — blue-black, deliberately not pure #000.
        ink: "#0A0E15",
        slab: "#0F1622", // primary panel
        raise: "#141E2C", // raised / hover surface
        edge: "#8FA6C4", // hairline source — used at low opacity (edge/12)
        // Text ramp.
        fg: "#E8EEF6",
        "fg-dim": "#8B9AB0",
        "fg-faint": "#5C6B82",
        // Brand beacon — verdigris (patina on a seal). Used sparingly.
        beacon: "#39D6C4",
        "beacon-deep": "#0E8073",
        // Earned signal palette (classification + trust). Distinct names so they
        // never collide with — or get diluted by — default Tailwind scales.
        jade: "#35C08A",
        azure: "#5AA2F0",
        gold: "#E7A93C",
        crimson: "#E85A5A",
      },
      fontFamily: {
        // System sans for headings + body (available offline everywhere).
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        // The identity carrier — structural labels, wordmark, hashes, data.
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Cascadia Code",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      letterSpacing: {
        eyebrow: "0.22em",
      },
      boxShadow: {
        panel: "inset 0 1px 0 rgba(255,255,255,0.03), 0 10px 30px -18px rgba(0,0,0,0.7)",
        lift: "0 20px 50px -20px rgba(0,0,0,0.75)",
        beacon: "0 0 0 1px rgba(57,214,196,0.4), 0 0 22px -6px rgba(57,214,196,0.45)",
        // Elevation tiers — a consistent top-lit hardware model. Each adds a
        // faint top highlight, a contact shadow, and a soft cast shadow.
        e1: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 1px rgba(0,0,0,0.4), 0 14px 28px -16px rgba(0,0,0,0.8)",
        e2: "inset 0 1px 0 rgba(255,255,255,0.06), 0 2px 6px rgba(0,0,0,0.45), 0 28px 56px -22px rgba(0,0,0,0.9)",
        e3: "inset 0 1px 0 rgba(255,255,255,0.07), 0 40px 80px -28px rgba(0,0,0,0.92)",
        // Recessed instrument well — data sits below the surface.
        well: "inset 0 2px 6px rgba(0,0,0,0.6), inset 0 -1px 0 rgba(255,255,255,0.03)",
        // Beveled key (primary action): bright top lip, solid base, cast glow.
        key: "inset 0 1px 0 rgba(233,255,251,0.55), 0 2px 0 #0a5f57, 0 10px 20px -6px rgba(57,214,196,0.4)",
        "key-press": "inset 0 2px 3px rgba(0,0,0,0.35), 0 1px 0 #0a5f57",
      },
      backgroundImage: {
        beam: "radial-gradient(1000px 520px at 50% -18%, rgba(57,214,196,0.07), transparent 62%)",
        seam: "linear-gradient(180deg, #0C121C 0%, #0A0E15 100%)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%,100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.35", transform: "scale(0.82)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)", opacity: "0" },
          "12%": { opacity: "1" },
          "88%": { opacity: "1" },
          "100%": { transform: "translateY(2200%)", opacity: "0" },
        },
        stamp: {
          "0%": { opacity: "0", transform: "scale(1.25) rotate(-4deg)" },
          "60%": { opacity: "1", transform: "scale(0.96) rotate(-4deg)" },
          "100%": { opacity: "1", transform: "scale(1) rotate(-4deg)" },
        },
        caret: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0" } },
        // The seal never turns edge-on (flat plates have no sides); it sways
        // through a 3/4 arc so the stacked relief always parallaxes into view.
        "seal-sway": {
          "0%,100%": { transform: "rotateX(11deg) rotateY(-24deg)" },
          "50%": { transform: "rotateX(16deg) rotateY(24deg)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "slide-up": "slide-up 0.32s cubic-bezier(0.16, 1, 0.3, 1)",
        "pulse-dot": "pulse-dot 2.4s ease-in-out infinite",
        scan: "scan 1.1s cubic-bezier(0.4, 0, 0.2, 1)",
        stamp: "stamp 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
        caret: "caret 1.1s step-end infinite",
        "seal-sway": "seal-sway 13s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
