export const fmtDuration = (s: number | null | undefined) => {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
};

export const fmtBytes = (b: number) =>
  b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`;

export const fmtMoney = (n: number) => (n < 0.01 && n > 0 ? "<$0.01" : `$${n.toFixed(2)}`);

export const fmtNumber = (n: number) =>
  n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n);

export function timeAgo(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export const editionDay = () => new Date().toLocaleDateString(undefined, { weekday: "long" });

export const STAGE_LABELS: Record<string, string> = {
  ingest: "Ingest",
  transcribe: "Transcribe",
  trends: "Trends",
  plan: "Moments",
  render: "Render",
  qc: "Quality check",
  copy: "Copy",
  deliver: "Deliver",
};
export const STAGES = Object.keys(STAGE_LABELS);
