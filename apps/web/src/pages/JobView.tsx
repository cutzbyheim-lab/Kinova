import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Download, RefreshCw, RotateCcw, ShieldCheck, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import PipelineBar from "../components/Pipeline";
import { Button, ErrorState, SectionHead, Skeleton, StatusChip } from "../components/ui";
import { api } from "../lib/api";
import { STAGE_LABELS, fmtDuration, fmtMoney, timeAgo } from "../lib/format";
import type { JobDetail, Output } from "../lib/types";

const VAR_COLORS = ["#FF6A2B", "#9A80FF", "#F4EDE4"];

function CutMap({ job }: { job: JobDetail }) {
  const total = job.source?.duration ?? job.source_media?.duration_s ?? 0;
  if (!total || job.outputs.length === 0) return null;
  return (
    <div className="card flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="m-0 text-[16px] font-semibold text-mute">Where each cut comes from</h3>
        <span className="font-mono text-[12px] text-dim">source · {fmtDuration(total)}</span>
      </div>
      <div className="flex flex-col gap-2.5">
        {job.outputs.map((o, i) => (
          <div key={o.id} className="flex items-center gap-3">
            <span className="serif-i w-20 shrink-0 text-[17px] capitalize" style={{ color: VAR_COLORS[i % 3] }}>{o.style}</span>
            <div className="relative h-6 flex-1 rounded-md bg-panel-3" role="img"
              aria-label={`${o.style} uses ${o.edit_plan.clips?.map((c) => `${fmtDuration(c.start)}–${fmtDuration(c.end)}`).join(", ")}`}>
              {o.edit_plan.clips?.map((c, k) => (
                <span key={k} className="absolute top-0 h-full rounded-[4px]"
                  style={{ left: `${(c.start / total) * 100}%`, width: `${Math.max(((c.end - c.start) / total) * 100, 0.6)}%`, background: VAR_COLORS[i % 3] }} />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-between font-mono text-[11px] text-faint"><span>0:00</span><span>{fmtDuration(total / 2)}</span><span>{fmtDuration(total)}</span></div>
    </div>
  );
}

function OutputCard({ o, index }: { o: Output; index: number }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState(o.title);
  const [caption, setCaption] = useState(o.caption);
  const [tags, setTags] = useState(o.hashtags.join(" "));
  useEffect(() => { setTitle(o.title); setCaption(o.caption); setTags(o.hashtags.join(" ")); }, [o.title, o.caption, o.hashtags]);
  const dirty = title !== o.title || caption !== o.caption || tags !== o.hashtags.join(" ");

  const save = useMutation({
    mutationFn: (patch: Partial<Output>) => api.updateOutput(o.id, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", o.job_id] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });
  const failedChecks = o.qc.checks?.filter((c) => !c.ok) ?? [];

  if (o.status !== "ready") {
    return (
      <article className="card flex flex-col gap-3 p-5">
        <span className="serif-i text-[22px] capitalize text-dim">{o.style}</span>
        {o.status === "rendering" ? <Skeleton className="aspect-[9/16]" /> : (
          <div className="flex aspect-[9/16] flex-col items-center justify-center gap-3 rounded-xl border border-danger/40 bg-[#2a1714] p-5 text-center">
            <AlertTriangle className="text-danger" aria-hidden />
            <p className="m-0 text-[14px]">This cut failed {o.qc.error ? "to render" : "quality checks"}.</p>
            <p className="m-0 text-[12px] text-dim">{o.qc.error ?? failedChecks.map((c) => `${c.name}: ${c.detail}`).join(" · ")}</p>
          </div>
        )}
      </article>
    );
  }

  return (
    <article className="card flex flex-col overflow-hidden animate-rise" style={{ animationDelay: `${index * 80}ms` }}>
      <div className="relative bg-black">
        <video src={o.url ?? undefined} poster={o.thumbnail_url ?? undefined} controls playsInline preload="metadata"
          className="aspect-[9/16] w-full object-contain" aria-label={`${o.style} cut preview`} />
        <span className="serif-i pointer-events-none absolute left-4 top-3 text-[26px] capitalize text-cream drop-shadow-[0_2px_6px_rgba(0,0,0,.8)]">{o.style}</span>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <span className="font-mono text-dim">{fmtDuration(o.duration_s)} · {o.width}×{o.height}</span>
          <details className="relative ml-auto">
            <summary className={`flex cursor-pointer list-none items-center gap-1 rounded-full border px-2.5 py-1 font-semibold ${o.qc.passed ? "border-ok/50 text-ok" : "border-warn/50 text-warn"}`}>
              {o.qc.passed ? <ShieldCheck size={14} aria-hidden /> : <ShieldAlert size={14} aria-hidden />} QC {o.qc.passed ? "passed" : "warnings"}
            </summary>
            <ul className="absolute right-0 z-10 mt-2 w-64 list-none rounded-xl border border-line-2 bg-panel-3 p-3 text-[12px] shadow-xl">
              {o.qc.checks?.map((c) => (
                <li key={c.name} className="flex justify-between gap-2 py-0.5">
                  <span className={c.ok ? "text-cream" : "text-warn"}>{c.ok ? "✓" : "!"} {c.name}</span>
                  <span className="truncate text-dim">{c.detail}</span>
                </li>
              ))}
            </ul>
          </details>
        </div>

        {o.edit_plan.reason && <p className="m-0 text-[13px] leading-snug text-dim">{o.edit_plan.reason}</p>}

        <div>
          <label className="label" htmlFor={`t-${o.id}`}>Title</label>
          <input id={`t-${o.id}`} className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add a title" />
        </div>
        <div>
          <label className="label" htmlFor={`c-${o.id}`}>Caption</label>
          <textarea id={`c-${o.id}`} className="field min-h-24 resize-y text-[14px]" value={caption} onChange={(e) => setCaption(e.target.value)}
            placeholder={o.caption ? "" : "No caption yet — connect Claude to have them written, or write your own."} />
        </div>
        <div>
          <label className="label" htmlFor={`h-${o.id}`}>Hashtags</label>
          <input id={`h-${o.id}`} className="field text-[14px]" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="#example #tags" />
        </div>
        {o.cta && <p className="m-0 text-[13px] text-mute"><span className="font-semibold text-cream">CTA:</span> {o.cta}</p>}

        <div className="mt-auto flex flex-wrap gap-2 pt-2">
          {dirty && (
            <Button variant="cream" busy={save.isPending}
              onClick={() => save.mutate({ title, caption, hashtags: tags.split(/\s+/).filter(Boolean).map((t) => (t.startsWith("#") ? t : `#${t}`)) })}>
              Save edits
            </Button>
          )}
          <Button variant={o.approved ? "cream" : "ghost"} icon={<Check size={16} aria-hidden />} busy={save.isPending && !dirty}
            onClick={() => save.mutate({ approved: !o.approved })} aria-pressed={o.approved}>
            {o.approved ? "Approved" : "Approve"}
          </Button>
          {o.download_url && (
            <a href={o.download_url} download
              className="inline-flex min-h-11 items-center gap-2 rounded-full bg-orange px-5 text-[15px] font-semibold text-ink no-underline transition-colors hover:bg-[#ff7f47]">
              <Download size={16} aria-hidden /> Download
            </a>
          )}
        </div>
        {save.isError && <ErrorState error={save.error} />}
      </div>
    </article>
  );
}

export default function JobView() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const job = useQuery({
    queryKey: ["job", id],
    queryFn: () => api.job(id),
    refetchInterval: (q) => (q.state.data && ["queued", "running"].includes(q.state.data.status) ? 1500 : false),
  });
  const retry = useMutation({ mutationFn: () => api.retryJob(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }) });
  const rerun = useMutation({ mutationFn: () => api.rerunJob(id), onSuccess: (j) => nav(`/studio/jobs/${j.id}`) });

  if (job.isLoading) return <div className="mx-auto flex max-w-[1320px] flex-col gap-6"><Skeleton className="h-24" /><Skeleton className="h-16" /><Skeleton className="h-96" /></div>;
  if (job.isError || !job.data) return <div className="mx-auto max-w-[1320px]"><ErrorState error={job.error} onRetry={() => job.refetch()} /></div>;
  const j = job.data;
  const live = j.status === "queued" || j.status === "running";
  const events = j.events.filter((e) => e.status !== "started" && e.status !== "progress");

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-5 animate-rise">
        <div className="flex flex-col gap-3">
          <Link to="/studio" className="eyebrow no-underline hover:text-cream">← Studio</Link>
          <h1 className="m-0 text-[clamp(38px,5vw,64px)] font-extrabold leading-[0.95] tracking-[-0.04em]">
            {j.project_name}{" "}
            <span className="serif-i text-orange">{live ? "in production." : j.status === "failed" ? "stopped." : "is cut."}</span>
          </h1>
          <div className="flex flex-wrap items-center gap-3 text-[14px] text-dim">
            <StatusChip status={j.status} />
            <span>{j.settings.platform} · {j.settings.variations} cut{j.settings.variations === 1 ? "" : "s"}</span>
            {j.settings.topic && <span>· topic “{j.settings.topic}”</span>}
            <span>· {timeAgo(j.created_at)}</span>
            <span>· AI cost {fmtMoney(j.cost_usd)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          {(j.status === "failed" || j.status === "partial") && (
            <Button icon={<RotateCcw size={16} aria-hidden />} busy={retry.isPending} onClick={() => retry.mutate()}>Resume</Button>
          )}
          {!live && <Button variant="cream" icon={<RefreshCw size={16} aria-hidden />} busy={rerun.isPending} onClick={() => rerun.mutate()}>Regenerate</Button>}
        </div>
      </header>

      <section className="flex flex-col gap-5 rounded-[var(--radius-card)] bg-panel-2 p-6">
        <PipelineBar job={j} events={j.events} />
        {live && j.stage && (
          <p className="m-0 text-[15px] text-mute" aria-live="polite">
            <span className="serif-i mr-2 text-[22px] text-orange">{STAGE_LABELS[j.stage]}…</span>
            {j.stage === "transcribe" && "The first run downloads the Whisper model, which can take a few minutes."}
            {j.stage === "render" && "Rendering vertical cuts with captions."}
          </p>
        )}
      </section>

      {j.error && <ErrorState error={new Error(j.error)} />}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex flex-col gap-6">
          <SectionHead num="01" title="The cuts" />
          {j.outputs.length ? (
            <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(210px,1fr))]">
              {j.outputs.map((o, i) => <OutputCard key={o.id} o={o} index={i} />)}
            </div>
          ) : (
            <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(210px,1fr))]">
              {Array.from({ length: j.settings.variations ?? 3 }).map((_, i) => (
                <div key={i} className="card flex flex-col gap-3 p-5">
                  <Skeleton className="aspect-[9/16]" />
                  <span className="text-[13px] text-dim">{live ? "Waiting for its turn…" : "Not produced"}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <aside className="flex flex-col gap-5">
          <div className="card flex flex-col gap-3 p-6">
            <span className="eyebrow">Editor's notes</span>
            {j.planner ? (
              <span className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-[13px] font-bold ${j.planner === "claude" ? "bg-violet text-ink" : "bg-warn text-ink"}`}>
                {j.planner === "claude" ? "Planned by Claude" : "Heuristic fallback — not AI"}
              </span>
            ) : <span className="text-[14px] text-dim">Planning hasn't run yet.</span>}
            {j.plan_summary && <p className="m-0 text-[14px] leading-relaxed text-mute">{j.plan_summary}</p>}
            {j.warnings.length > 0 && (
              <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
                {j.warnings.map((w, i) => <li key={i} className="text-[13px] leading-snug text-warn">⚠ {w}</li>)}
              </ul>
            )}
          </div>

          <CutMap job={j} />

          {j.trends && j.trends.sample_size > 0 && (
            <div className="card flex flex-col gap-3 p-6">
              <span className="eyebrow">Trend brief · YouTube</span>
              <p className="m-0 text-[14px] text-mute">
                {j.trends.sample_size} top videos · median {j.trends.median_duration_s}s · {Math.round((j.trends.shorts_share ?? 0) * 100)}% Shorts
              </p>
              {j.trends.top_keywords && (
                <div className="flex flex-wrap gap-1.5">
                  {j.trends.top_keywords.slice(0, 10).map((k) => <span key={k} className="rounded-full border border-line-3 px-2.5 py-0.5 text-[12px] text-mute">{k}</span>)}
                </div>
              )}
            </div>
          )}

          <div className="card flex flex-col gap-3 p-6">
            <span className="eyebrow">Production log</span>
            <ol className="m-0 flex list-none flex-col gap-3 p-0">
              {events.map((e, i) => (
                <li key={i} className="flex gap-3 text-[13px] leading-snug">
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${e.status === "done" ? "bg-orange" : e.status === "skipped" ? "bg-line-3" : "bg-danger"}`} aria-hidden />
                  <span><strong className="text-cream">{STAGE_LABELS[e.stage] ?? e.stage}</strong>{" "}
                    <span className="text-dim">{e.status === "skipped" ? "skipped — " : e.status === "failed" ? "failed — " : ""}{e.message}</span></span>
                </li>
              ))}
              {live && <li className="text-[13px] text-dim">…</li>}
            </ol>
          </div>
        </aside>
      </div>
    </div>
  );
}
