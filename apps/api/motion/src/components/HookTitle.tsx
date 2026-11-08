import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Theme } from "../theme";

/** Index of the word that gets the hero pill: the longest, ties go to the later word. */
export const highlightIndex = (words: string[]) =>
  words.reduce((best, w, i) => (w.replace(/[^\p{L}\p{N}]/gu, "").length >= words[best]!.replace(/[^\p{L}\p{N}]/gu, "").length ? i : best), 0);

export const HookTitle: React.FC<{ text: string; endFrame: number; theme: Theme }> = ({ text, endFrame, theme }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (!words.length || frame > endFrame) return null;
  const hi = highlightIndex(words);
  const startAt = 2; // something moves in the first frames
  const stagger = Math.round(theme.timing.wordStagger * fps);
  const exitStagger = Math.max(1, Math.round(theme.timing.exitWordStagger * fps));
  const exitLen = Math.round(theme.timing.exit * fps);
  const breathe = 1 + Math.sin(frame / 22) * 0.012;

  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          top: height * theme.layout.hookTop,
          width: theme.layout.textWidth,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          columnGap: 22,
          rowGap: 10,
          transform: `scale(${breathe})`,
        }}
      >
        {words.map((w, i) => {
          const p = spring({ frame: frame - startAt - i * stagger, fps, config: theme.spring.snappy });
          const exitStart = endFrame - exitLen - (words.length - 1 - i) * exitStagger;
          const ex = interpolate(frame, [exitStart, exitStart + exitLen * 0.6], [0, 1], {
            easing: theme.ease.in,
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const isHi = i === hi && words.length > 1;
          const pill = isHi
            ? spring({ frame: frame - startAt - i * stagger - Math.round(theme.timing.pillDelay * fps), fps, config: theme.spring.snappy })
            : 0;
          return (
            <span
              key={i}
              style={{
                position: "relative",
                display: "inline-block",
                padding: isHi ? "0 18px" : 0,
                fontFamily: theme.fonts.display,
                fontWeight: 800,
                fontSize: 104,
                lineHeight: 1.05,
                letterSpacing: "-0.03em",
                textTransform: "uppercase",
                color: isHi && pill > 0.5 ? theme.colors.ink : theme.colors.text,
                textShadow: isHi && pill > 0.5 ? "none" : `0 6px 28px ${theme.colors.shadow}`,
                opacity: Math.min(p * 1.3, 1) * (1 - ex),
                transform: `translateY(${interpolate(p, [0, 1], [46, 0]) + interpolate(ex, [0, 1], [0, -40])}px) scale(${interpolate(p, [0, 1], [0.88, 1])})`,
              }}
            >
              {isHi && (
                <span
                  aria-hidden
                  style={{
                    position: "absolute",
                    inset: "6px 0 2px 0",
                    borderRadius: 22,
                    background: theme.colors.hero,
                    boxShadow: `0 0 60px ${theme.colors.hero}66`,
                    transformOrigin: "0% 50%",
                    transform: `scaleX(${pill})`,
                    zIndex: -1,
                  }}
                />
              )}
              {w}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
