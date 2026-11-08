/** Input props KINOVA's worker sends for one finished cut. All times are in seconds. */
export type Word = { start: number; end: number; text: string };

export type BRollShot = { src: string; at: number; duration: number };

export type CutProps = {
  /** Set by render.mjs: where the local asset server lives. */
  baseUrl: string;
  /** File name of the assembled cut (FFmpeg output) inside the asset server. */
  video: string;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  colors: { hero: string; accent: string };
  /** Start time of every clip inside the cut — the footage breathes per segment. */
  segments: number[];
  hook: string;
  words: Word[];
  captionPosition: "center" | "bottom";
  broll: BRollShot[];
  cta: string;
  /** Seconds. Hook title is on screen until hookEnd (0 = no hook); CTA from ctaStart (>= duration = none). */
  hookEnd: number;
  ctaStart: number;
};

export const defaultProps: CutProps = {
  baseUrl: "",
  video: "",
  width: 1080,
  height: 1920,
  fps: 30,
  durationInFrames: 300,
  colors: { hero: "#FF6A2B", accent: "#9A80FF" },
  segments: [0],
  hook: "Nobody tells you this",
  words: [],
  captionPosition: "center",
  broll: [],
  cta: "",
  hookEnd: 2.8,
  ctaStart: 10,
};
