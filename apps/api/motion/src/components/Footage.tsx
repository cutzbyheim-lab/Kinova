import { AbsoluteFill, OffthreadVideo, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { Theme } from "../theme";

const PUSH = 1.03;

/** The assembled cut. Each clip segment gets a slow push-in so the footage never sits dead still. */
export const Footage: React.FC<{ src: string; segments: number[]; theme: Theme }> = ({ src, segments, theme }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const starts = segments.map((s) => Math.round(s * fps));
  const i = Math.max(0, starts.findLastIndex((s) => s <= frame));
  const from = starts[i] ?? 0;
  const to = starts[i + 1] ?? durationInFrames;
  const scale = interpolate(frame, [from, to], [1, PUSH], {
    easing: theme.ease.inOut,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <OffthreadVideo
        src={src}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }}
      />
    </AbsoluteFill>
  );
};
