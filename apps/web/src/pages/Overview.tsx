import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Upload } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import ClipTile from "../components/ClipTile";
import PipelineBar from "../components/Pipeline";
import { Dot, EmptyState, ErrorState, LinkButton, SectionHead, Skeleton, Stat, StatusChip, gradientFor } from "../components/ui";
import { api } from "../lib/api";
import { STAGES, editionDay, fmtMoney, fmtNumber, timeAgo } from "../lib/format";

export default function Overview() {
  const nav = useNavigate();
  const [ask, setAsk] = useState("");
  const status = useQuery({ queryKey: ["status"], queryFn: api.status });
  const ov = useQuery({
    queryKey: ["overview"],
    queryFn: api.overview,
    refetchInterval: (q) => (q.state.data?.active_job ? 3000 : 20_000),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    nav(`/studio/new${ask.trim() ? `?goal=${encodeURIComponent(ask.trim())}` : ""}`);
  };

  const d = ov.data;
  const featuredJob = d?.active_job ?? d?.latest_job ?? null;
  const featuredOutputs = d?.recent_outputs.filter((o) => o.job_id === d?.latest_job?.id) ?? [];
  const hero = featuredOutputs[0] ?? d?.recent_outputs[0];
  const stageIdx = featuredJob ? (featuredJob.stage ? STAGES.indexOf(featuredJob.stage) + 1 : STAGES.length) : 0;

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-9">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="eyebrow flex gap-3"><span>Overview</span><span aria-hidden>—</span><span>{editionDay()} edition</span></div>
        <div className="flex flex-wrap gap-2.5">
          <Dot on={!!status.data?.worker.online} label={status.data?.worker.online ? "Worker ready" : "Worker offline"} />
          <Dot on={!!status.data?.integrations.claude.configured}
            label={status.data?.integrations.claude.configured ? "Claude connected" : "Claude key missing"} />
          <Dot on={!!status.data?.integrations.youtube.configured}
            label={status.data?.integrations.youtube.configured ? "YouTube trends on" : "YouTube not connected"} />
        </div>
      </div>

      {ov.isError && <ErrorState error={ov.error} onRetry={() => ov.refetch()} />}

      {/* Hero */}
      <section className="flex flex-wrap items-stretch gap-11">
        <div className="flex min-w-[300px] flex-[1_1_380px] flex-col justify-between gap-7 animate-rise">
          <h1 className="m-0 text-[clamp(56px,7.4vw,98px)] font-extrabold leading-[0.9] tracking-[-0.05em]">
            Raw in.<br /><span className="serif-i tracking-[-0.02em] text-orange">Remarkable</span> out.
          </h1>
          <p className="m-0 max-w-[460px] text-[19px] leading-relaxed text-mute">
            Upload footage and KINOVA finds the moments, cuts the clips and writes the copy — shaped by what's trending in your space.
          </p>
          <form onSubmit={submit} className="flex flex-wrap gap-2 rounded-[22px] border border-line-2 bg-panel-2 p-2 focus-within:border-orange transition-colors">
            <label htmlFor="ask" className="sr-only">Tell KINOVA what to make</label>
            <input id="ask" value={ask} onChange={(e) => setAsk(e.target.value)}
              placeholder="Turn my latest upload into 3 TikToks…"
              className="min-h-12 flex-[1_1_220px] border-0 bg-transparent px-3.5 text-[16px] text-cream outline-none placeholder:text-faint" />
            <button type="submit" className="inline-flex min-h-12 items-center gap-2 rounded-2xl bg-orange px-6 text-[15px] font-bold text-ink transition-colors hover:bg-[#ff7f47]">
              Produce <ArrowRight size={17} aria-hidden />
            </button>
          </form>
        </div>

        <div className="flex min-w-0 flex-[1.35_1_500px] gap-3.5">
          {ov.isLoading ? <Skeleton className="aspect-video w-full" /> : hero ? (
            <>
              <Link to={`/studio/jobs/${hero.job_id}`}
                className="group relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-card)] border border-line bg-panel no-underline">
                <div className="relative flex-1 overflow-hidden" style={{ background: gradientFor(hero.id), minHeight: 300 }}>
                  {hero.thumbnail_url && (
                    <img src={hero.thumbnail_url} alt="" className="absolute inset-0 h-full w-full object-cover opacity-90 blur-[1px] scale-110" />
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-ink via-ink/30 to-transparent" />
                  {hero.thumbnail_url && (
                    <img src={hero.thumbnail_url} alt={`Frame from ${hero.title || hero.style} cut`}
                      className="absolute left-1/2 top-1/2 h-[86%] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line-2 shadow-2xl transition-transform duration-500 group-hover:scale-[1.03]" />
                  )}
                  <span className="absolute left-4 top-4 rounded-full bg-cream px-3 py-1 text-[12px] font-bold text-ink">Latest cut</span>
                </div>
                <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-4">
                  <span className="text-[17px] font-bold">{hero.title || `${hero.style} cut`}</span>
                  <span className="text-[13px] text-dim">{timeAgo(hero.created_at)} · open in Studio →</span>
                </div>
              </Link>
              {featuredOutputs.length > 1 && (
                <div className="hidden w-24 shrink-0 flex-col gap-2.5 sm:flex">
                  {featuredOutputs.slice(0, 3).map((o) => (
                    <Link key={o.id} to={`/studio/jobs/${o.job_id}`} className="relative flex-1 overflow-hidden rounded-2xl border border-line no-underline"
                      style={{ background: gradientFor(o.id) }}>
                      {o.thumbnail_url && <img src={o.thumbnail_url} alt="" className="absolute inset-0 h-full w-full object-cover" />}
                      <span className="serif-i absolute bottom-2 left-2 text-[18px] capitalize text-cream drop-shadow">{o.style}</span>
                    </Link>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-1 flex-col justify-end gap-4 rounded-[var(--radius-card)] border border-dashed border-line-3 p-8"
              style={{ background: "radial-gradient(90% 80% at 75% 20%, rgba(255,106,43,.22), transparent 60%), #1a1513", minHeight: 320 }}>
              <span className="serif-i text-[64px] leading-none text-violet">00</span>
              <p className="m-0 text-[26px] font-semibold leading-tight">Your first cut lands here.</p>
              <p className="m-0 max-w-md text-[15px] text-mute">Drop in a video — a talk, a tutorial, a behind-the-scenes take — and KINOVA turns it into ready-to-post vertical clips.</p>
              <div><LinkButton to="/studio/new" variant="primary" icon={<Upload size={17} aria-hidden />}>Upload footage</LinkButton></div>
            </div>
          )}
        </div>
      </section>

      {/* Pipeline */}
      <section aria-label="Production pipeline" className="flex flex-wrap items-center gap-5 rounded-[var(--radius-card)] bg-panel-2 px-6 py-5">
        {featuredJob ? (
          <>
            <Link to={`/studio/jobs/${featuredJob.id}`} className="flex flex-col gap-1 no-underline">
              <span className="eyebrow">{d?.active_job ? "Now producing" : "Last production"}</span>
              <StatusChip status={featuredJob.status} />
            </Link>
            <div className="min-w-[280px] flex-[1_1_520px]"><PipelineBar job={featuredJob} compact /></div>
            <span className="serif-i text-[30px] text-orange">{Math.min(stageIdx, STAGES.length - 1)} / {STAGES.length - 1}</span>
          </>
        ) : (
          <p className="m-0 text-[15px] text-mute"><span className="eyebrow mr-3">Pipeline</span>Idle — nothing in production yet.</p>
        )}
      </section>

      {/* Stats */}
      <section aria-label="Studio totals" className="grid grid-cols-2 gap-6 border-y border-line-2 py-6 md:grid-cols-4">
        <Stat label="Footage in" value={d ? `${d.stats.footage_minutes}m` : "—"} hint={`${d?.stats.uploads ?? 0} uploads`} />
        <Stat label="Clips ready" value={d ? fmtNumber(d.stats.clips_ready) : "—"} />
        <Stat label="Approved" value={d ? fmtNumber(d.stats.clips_approved) : "—"} />
        <Stat label="AI spend" value={d ? fmtMoney(d.stats.ai_spend_month_usd) : "—"} hint="this month" />
      </section>

      {/* Sections */}
      <section className="grid gap-10 [grid-template-columns:repeat(auto-fit,minmax(280px,1fr))]">
        <div className="flex flex-col gap-4">
          <SectionHead num="01" title="Fresh off the desk" action={<Link to="/library" className="text-[14px] font-bold">Library →</Link>} />
          {d && d.recent_outputs.length > 0 ? (
            <div className="grid grid-cols-3 gap-2.5">
              {d.recent_outputs.slice(0, 3).map((o) => <ClipTile key={o.id} o={o} to={`/studio/jobs/${o.job_id}`} />)}
            </div>
          ) : ov.isLoading ? <div className="grid grid-cols-3 gap-2.5">{[0, 1, 2].map((i) => <Skeleton key={i} className="aspect-[9/16]" />)}</div> : (
            <p className="m-0 text-[15px] leading-relaxed text-mute">Finished clips appear here the moment they pass quality checks.</p>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <SectionHead num="02" title="What's trending" />
          {featuredJob?.trends && featuredJob.trends.sample_size > 0 ? (
            <>
              <p className="m-0 text-[15px] text-mute">Top YouTube videos for <strong className="text-cream">“{featuredJob.trends.topic}”</strong>, last 30 days</p>
              <ul className="m-0 flex list-none flex-col p-0">
                {featuredJob.trends.top_videos?.slice(0, 4).map((v, i) => (
                  <li key={i} className="flex items-baseline gap-3 border-b border-line py-2.5">
                    <span className="serif-i w-6 shrink-0 text-[20px] text-violet">{i + 1}</span>
                    <span className="min-w-0 flex-1 truncate text-[15px] font-semibold">{v.title}</span>
                    <span className="shrink-0 font-mono text-[12px] text-dim">{fmtNumber(v.views)}</span>
                  </li>
                ))}
              </ul>
              <p className="m-0 text-[13px] text-dim">
                Median length {featuredJob.trends.median_duration_s ?? "—"}s · {Math.round((featuredJob.trends.shorts_share ?? 0) * 100)}% are Shorts
              </p>
            </>
          ) : (
            <>
              <p className="m-0 text-[26px] font-semibold leading-tight">
                The trend desk is <span className="serif-i text-orange">quiet</span>{" "}
                {status.data?.integrations.youtube.configured ? "until your first production." : "until YouTube is connected."}
              </p>
              <p className="m-0 text-[15px] leading-relaxed text-mute">Then it ranks the hooks, lengths and titles winning in your topic this month — and every cut is shaped by it.</p>
              {!status.data?.integrations.youtube.configured && <Link to="/settings" className="text-[15px] font-bold">Connect YouTube →</Link>}
            </>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <SectionHead num="03" title="Brand brain" />
          {d?.brand ? (
            <>
              <div className="grid grid-cols-2 gap-2">
                {(d.brand.colors.length ? d.brand.colors : ["#FF6A2B", "#9A80FF"]).slice(0, 4).map((c) => (
                  <div key={c} className="h-16 rounded-2xl border border-line-2" style={{ background: c }} title={c} />
                ))}
              </div>
              <p className="m-0 text-[15px] leading-relaxed text-mute">
                <strong className="text-cream">{d.brand.name}</strong>{d.brand.voice ? ` — ${d.brand.voice}` : " — add a voice so captions sound like you."}
              </p>
              <Link to="/brands" className="text-[15px] font-bold">Edit brand →</Link>
            </>
          ) : (
            <>
              <p className="m-0 text-[15px] leading-relaxed text-mute">Teach KINOVA your colors, voice and audience once. Every clip, caption and campaign uses it.</p>
              <div><LinkButton to="/brands" variant="cream">Set up a brand</LinkButton></div>
            </>
          )}
        </div>
      </section>

      {d && d.recent_jobs.length === 0 && !ov.isLoading && (
        <EmptyState title="Three steps to your first clips." body="1 · Upload a video in the Studio. 2 · Tell KINOVA the topic and goal. 3 · Review, tweak and download the cuts.">
          <LinkButton to="/studio/new" variant="primary">Open the Studio</LinkButton>
          <LinkButton to="/settings">Check connections</LinkButton>
        </EmptyState>
      )}
    </div>
  );
}
