// theme.ts — single source of truth for KINOVA's motion layer.
// NEVER inline colors, easings, or spring configs in components.
import { Easing } from "remotion";

const base = {
  colors: {
    ink: "#15110F",
    text: "#F4EDE4",
    shadow: "rgba(0, 0, 0, 0.55)",
    shadeTop: "rgba(0, 0, 0, 0.38)",
    shadeBottom: "rgba(0, 0, 0, 0.42)",
    clear: "rgba(0, 0, 0, 0)",
  },
  fonts: {
    display: "Poppins",
  },
  // THE easing curves. Linear is forbidden.
  ease: {
    out: Easing.bezier(0.16, 1, 0.3, 1), // easeOutExpo — entrances
    inOut: Easing.bezier(0.83, 0, 0.17, 1), // easeInOutQuint — pushes, drifts
    in: Easing.bezier(0.7, 0, 0.84, 0), // exits only
  },
  spring: {
    snappy: { damping: 14, stiffness: 160, mass: 0.6 }, // words, caption pops
    smooth: { damping: 20, stiffness: 90, mass: 1 }, // b-roll, big elements
    bouncy: { damping: 11, stiffness: 170, mass: 0.7 }, // CTA
  },
  // Timing in seconds; components convert with fps.
  timing: {
    wordStagger: 0.1, // 3 frames @30fps
    exitWordStagger: 0.066, // 2 frames
    exit: 0.33, // 10 frames — faster than entrances
    pillDelay: 0.17, // 5 frames after the word lands
  },
  layout: {
    hookTop: 0.22,
    ctaTop: 0.26,
    captionCenter: 0.62,
    captionBottom: 0.72,
    textWidth: 920,
  },
} as const;

export type Theme = typeof base & { colors: typeof base.colors & { hero: string; accent: string } };

export const makeTheme = (brand: { hero: string; accent: string }): Theme => ({
  ...base,
  colors: { ...base.colors, hero: brand.hero, accent: brand.accent },
});
