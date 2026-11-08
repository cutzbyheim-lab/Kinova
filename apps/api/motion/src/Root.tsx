import { Composition } from "remotion";
import { KinovaCut } from "./KinovaCut";
import { defaultProps, type CutProps } from "./types";

export const Root: React.FC = () => (
  <Composition
    id="KinovaCut"
    component={KinovaCut}
    width={defaultProps.width}
    height={defaultProps.height}
    fps={defaultProps.fps}
    durationInFrames={defaultProps.durationInFrames}
    defaultProps={defaultProps}
    calculateMetadata={({ props }: { props: CutProps }) => ({
      durationInFrames: Math.max(1, Math.round(props.durationInFrames)),
      width: props.width,
      height: props.height,
      fps: props.fps,
    })}
  />
);
