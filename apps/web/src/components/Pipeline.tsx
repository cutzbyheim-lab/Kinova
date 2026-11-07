import type { Job, JobEvent } from "../lib/types";
import { STAGES, STAGE_LABELS } from "../lib/format";

type StageState = "done" | "skipped" | "active" | "failed" | "pending";

export function stageStates(job: Job, events: JobEvent[] = []): Record<string, StageState> {
  const out: Record<string, StageState> = {};
  const last: Record<string, string> = {};
  for (const e of events) if (e.status !== "progress") last[e.stage] = e.status;
  const doneIdx = job.status === "succeeded" || job.status === "partial" ? STAGES.length : STAGES.indexOf(job.stage ?? "");
  STAGES.forEach((s, i) => {
    if (last[s] === "failed" || (job.status === "failed" && job.stage === s)) out[s] = "failed";
    else if (last[s] === "skipped" || job.skipped_stages?.includes(s)) out[s] = "skipped";
    else if (last[s] === "done" || i < doneIdx) out[s] = "done";
    else if (job.stage === s && job.status === "running") out[s] = "active";
    else out[s] = "pending";
  });
  return out;
}

const bar: Record<StageState, string> = {
  done: "bg-orange",
  skipped: "bg-line-3",
  active: "striped",
  failed: "bg-danger",
  pending: "bg-line-2",
};

export default function PipelineBar({ job, events, compact }: { job: Job; events?: JobEvent[]; compact?: boolean }) {
  const states = stageStates(job, events);
  const stages = compact ? STAGES.filter((s) => s !== "deliver") : STAGES;
  return (
    <ol className="m-0 grid list-none gap-1.5 p-0" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}
      aria-label="Production stages">
      {stages.map((s) => {
        const st = states[s]!;
        return (
          <li key={s} className="flex min-w-0 flex-col gap-2">
            <div className={`h-2 rounded-full transition-colors duration-500 ${bar[st]}`} />
            <span className={`truncate text-[13px] font-semibold ${st === "pending" ? "text-faint" : st === "skipped" ? "text-dim line-through decoration-line-3" : "text-cream"}`}>
              {STAGE_LABELS[s]}
              <span className="sr-only"> — {st}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
