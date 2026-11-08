import { useEffect, useState } from "react";
import { AbsoluteFill, Sequence, continueRender, delayRender, useVideoConfig } from "remotion";
import { BRoll } from "./components/BRoll";
import { Captions } from "./components/Captions";
import { Cta } from "./components/Cta";
import { Footage } from "./components/Footage";
import { Shade } from "./components/Finish";
import { HookTitle } from "./components/HookTitle";
import { fontsReady } from "./fonts";
import { makeTheme } from "./theme";
import type { CutProps } from "./types";

/**
 * One finished vertical cut. Layer stack, bottom → top:
 * ink base → footage + B-roll (assets) → shade → hook / captions / CTA (type).
 * Grade, grain and vignette go on top in the worker's final FFmpeg pass.
 */
export const KinovaCut: React.FC<CutProps> = (props) => {
  const { fps, durationInFrames } = useVideoConfig();
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    fontsReady.then(() => continueRender(handle)).catch(() => continueRender(handle));
  }, [handle]);

  const theme = makeTheme(props.colors);
  const hookEnd = props.hook.trim() ? Math.round(props.hookEnd * fps) : 0;
  const ctaStart = props.cta.trim() ? Math.min(Math.round(props.ctaStart * fps), durationInFrames) : durationInFrames;
  const hasCta = ctaStart < durationInFrames;
  // One hero-colored element per frame: hook pill, then captions, then the CTA.
  const heroFree = (f: number) => f > hookEnd && f < ctaStart;

  return (
    <AbsoluteFill style={{ backgroundColor: theme.colors.ink }}>
      <Footage src={props.baseUrl + props.video} segments={props.segments} theme={theme} />
      <BRoll shots={props.broll} baseUrl={props.baseUrl} theme={theme} />
      <Shade theme={theme} />
      <Captions words={props.words} position={props.captionPosition} theme={theme} heroFree={heroFree} />
      {hookEnd > 0 && <HookTitle text={props.hook} endFrame={hookEnd} theme={theme} />}
      {hasCta && (
        <Sequence from={ctaStart} durationInFrames={durationInFrames - ctaStart} layout="none">
          <Cta text={props.cta} theme={theme} />
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
