import { AbsoluteFill, OffthreadVideo, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { BRollShot } from "../types";
import type { Theme } from "../theme";

const Shot: React.FC<{ src: string; theme: Theme }> = ({ src, theme }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const exitLen = Math.round(theme.timing.exit * fps * 0.7);
  // Entrance: fade + scale-down + de-blur together
  const p = spring({ frame, fps, config: theme.spring.smooth });
  // Exit: faster, eased in
  const e = interpolate(frame, [durationInFrames - exitLen, durationInFrames], [0, 1], {
    easing: theme.ease.in,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Ken Burns push for the hold
  const push = interpolate(frame, [0, durationInFrames], [1, 1.06], {
    easing: theme.ease.inOut,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = interpolate(p, [0, 1], [1.12, 1]) * push * interpolate(e, [0, 1], [1, 1.04]);
  return (
    <AbsoluteFill
      style={{
        opacity: Math.min(p * 1.4, 1) * (1 - e),
        filter: p < 0.97 ? `blur(${interpolate(p, [0, 1], [10, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px)` : undefined,
        overflow: "hidden",
      }}
    >
      <OffthreadVideo
        src={src}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }}
      />
    </AbsoluteFill>
  );
};

export const BRoll: React.FC<{ shots: BRollShot[]; baseUrl: string; theme: Theme }> = ({ shots, baseUrl, theme }) => {
  const { fps } = useVideoConfig();
  return (
    <>
      {shots.map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * fps)} durationInFrames={Math.max(1, Math.round(s.duration * fps))} layout="none">
          <Shot src={baseUrl + s.src} theme={theme} />
        </Sequence>
      ))}
    </>
  );
};
