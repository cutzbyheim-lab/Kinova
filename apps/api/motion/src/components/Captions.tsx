import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Word } from "../types";
import type { Theme } from "../theme";

type Page = { start: number; end: number; words: Word[] };

const MAX_WORDS = 3;
const MAX_CHARS = 16;
const MAX_GAP = 0.5;

/** Groups words into short caption pages (2–3 words), breaking on pauses and punctuation. */
export const toPages = (words: Word[]): Page[] => {
  const pages: Page[] = [];
  let cur: Word[] = [];
  const flush = () => {
    if (cur.length) pages.push({ start: cur[0]!.start, end: cur[cur.length - 1]!.end, words: cur });
    cur = [];
  };
  for (const w of words) {
    const last = cur[cur.length - 1];
    if (last) {
      const len = cur.map((x) => x.text).join(" ").length + 1 + w.text.length;
      if (cur.length >= MAX_WORDS || len > MAX_CHARS || w.start - last.end > MAX_GAP) flush();
    }
    cur.push(w);
    if (/[.?!,]$/.test(w.text)) flush();
  }
  flush();
  // Hold each page until the next one starts when the gap is short, so captions don't flicker.
  pages.forEach((p, i) => {
    const next = pages[i + 1];
    p.end = next && next.start - p.end < 0.35 ? next.start : p.end + 0.2;
  });
  return pages;
};

const CaptionPage: React.FC<{ page: Page; theme: Theme; top: number; heroFree: (absFrame: number) => boolean; offset: number }> = ({
  page, theme, top, heroFree, offset,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = page.start + frame / fps;
  const exitLen = Math.round(theme.timing.exit * fps * 0.5);
  const ex = interpolate(frame, [durationInFrames - exitLen, durationInFrames], [0, 1], {
    easing: theme.ease.in,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const useHero = heroFree(offset + frame);
  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          top,
          width: theme.layout.textWidth,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          columnGap: 30, // px, not em; leaves room for the active word's scale-up
          rowGap: 4,
          transform: "translateY(-50%)",
          opacity: 1 - ex,
        }}
      >
        {page.words.map((w, i) => {
          const local = Math.round((w.start - page.start) * fps);
          const p = spring({ frame: frame - local, fps, config: theme.spring.snappy });
          const active = t >= w.start - 0.02 && t < w.end + 0.08;
          const lift = spring({ frame: active ? frame - local : 0, fps, config: theme.spring.snappy, durationInFrames: 8 });
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                fontFamily: theme.fonts.display,
                fontWeight: 800,
                fontSize: 86,
                lineHeight: 1.08,
                letterSpacing: "-0.01em",
                textTransform: "uppercase",
                color: active && useHero ? theme.colors.hero : theme.colors.text,
                WebkitTextStroke: `12px ${theme.colors.ink}`,
                paintOrder: "stroke fill",
                textShadow: `0 8px 26px ${theme.colors.shadow}`,
                opacity: Math.min(p * 1.4, 1),
                transform: `translateY(${interpolate(p, [0, 1], [26, 0])}px) scale(${interpolate(p, [0, 1], [0.8, 1]) * (active ? 1 + 0.07 * lift : 1)})`,
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Captions: React.FC<{
  words: Word[];
  position: "center" | "bottom";
  theme: Theme;
  heroFree: (absFrame: number) => boolean;
}> = ({ words, position, theme, heroFree }) => {
  const { fps, height } = useVideoConfig();
  const top = height * (position === "center" ? theme.layout.captionCenter : theme.layout.captionBottom);
  return (
    <>
      {toPages(words).map((page, i) => {
        const from = Math.round(page.start * fps);
        const dur = Math.max(1, Math.round(page.end * fps) - from);
        return (
          <Sequence key={i} from={from} durationInFrames={dur} layout="none">
            <CaptionPage page={page} theme={theme} top={top} heroFree={heroFree} offset={from} />
          </Sequence>
        );
      })}
    </>
  );
};
