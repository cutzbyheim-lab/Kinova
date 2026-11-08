import { AbsoluteFill } from "remotion";
import type { Theme } from "../theme";

/**
 * Top/bottom shading that keeps type legible over any footage.
 * The color grade, film grain and vignette are applied on top of the whole frame
 * by the worker's final FFmpeg pass (same layer order, ~30% faster than in-browser).
 */
export const Shade: React.FC<{ theme: Theme }> = ({ theme }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: `linear-gradient(180deg, ${theme.colors.shadeTop}, ${theme.colors.clear} 34%, ${theme.colors.clear} 56%, ${theme.colors.shadeBottom})`,
    }}
  />
);
