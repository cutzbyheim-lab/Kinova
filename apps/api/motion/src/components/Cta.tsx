import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Theme } from "../theme";

/** Closing call-to-action pill. Owns the hero color (and the only glow) while on screen. */
export const Cta: React.FC<{ text: string; theme: Theme }> = ({ text, theme }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, height } = useVideoConfig();
  const exitLen = Math.round(theme.timing.exit * fps * 0.8);
  const p = spring({ frame: frame - 2, fps, config: theme.spring.bouncy });
  const ex = interpolate(frame, [durationInFrames - exitLen, durationInFrames], [0, 1], {
    easing: theme.ease.in,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const breathe = 1 + Math.sin(frame / 18) * 0.018;
  const arrow = spring({ frame: frame - 9, fps, config: theme.spring.snappy });
  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          top: height * theme.layout.ctaTop,
          display: "flex",
          alignItems: "center",
          gap: 22,
          padding: "26px 44px",
          borderRadius: 999,
          background: theme.colors.hero,
          boxShadow: `0 0 60px ${theme.colors.hero}66, 0 0 120px ${theme.colors.hero}33`,
          opacity: Math.min(p * 1.3, 1) * (1 - ex),
          transform: `translateY(${interpolate(p, [0, 1], [50, 0]) - ex * 30}px) scale(${interpolate(p, [0, 1], [0.7, 1]) * breathe})`,
        }}
      >
        <span
          style={{
            fontFamily: theme.fonts.display,
            fontWeight: 800,
            fontSize: 66,
            lineHeight: 1,
            letterSpacing: "-0.02em",
            textTransform: "uppercase",
            color: theme.colors.ink,
          }}
        >
          {text}
        </span>
        <svg width="58" height="58" viewBox="0 0 24 24" aria-hidden
          style={{ transform: `translateX(${interpolate(arrow, [0, 1], [-14, 0])}px)`, opacity: arrow }}>
          <path d="M4 12h15M13 6l6 6-6 6" fill="none" stroke={theme.colors.ink} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </AbsoluteFill>
  );
};
