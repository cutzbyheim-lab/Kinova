import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, PlugZap } from "lucide-react";
import type { ReactNode } from "react";
import { Button, ErrorState, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";

function ClaudeTest() {
  const test = useMutation({ mutationFn: api.checkClaude });
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button icon={<PlugZap size={16} aria-hidden />} busy={test.isPending} onClick={() => test.mutate()}>Test connection</Button>
      {test.data && (
        <span role="status" className={`text-[14px] ${test.data.ok ? "text-ok" : "text-danger"}`}>
          {test.data.ok ? `Working — ${test.data.model} answered.` : test.data.error}
        </span>
      )}
      {test.isError && <span role="status" className="text-[14px] text-danger">{(test.error as Error).message}</span>}
    </div>
  );
}

function Integration({ name, on, what, env, how, extra, children }:
  { name: string; on: boolean; what: string; env: string; how: ReactNode; extra?: string; children?: ReactNode }) {
  return (
    <section className="card flex flex-col gap-4 p-6">
      <div className="flex items-center gap-3">
        {on ? <CheckCircle2 className="text-ok" aria-hidden /> : <CircleDashed className="text-dim" aria-hidden />}
        <h2 className="m-0 text-[22px] font-bold">{name}</h2>
        <span className={`ml-auto rounded-full px-3 py-1 text-[13px] font-bold ${on ? "bg-ok text-ink" : "border border-line-3 text-mute"}`}>
          {on ? "Connected" : "Not connected"}
        </span>
      </div>
      <p className="m-0 text-[15px] leading-relaxed text-mute">{what}</p>
      {extra && <p className="m-0 font-mono text-[13px] text-dim">{extra}</p>}
      {children}
      {!on && (
        <div className="rounded-2xl bg-panel-2 p-4 text-[14px] leading-relaxed text-mute">
          {how}
          <p className="mb-0 mt-3">Then add it to the <code className="rounded bg-panel-3 px-1.5 py-0.5 font-mono text-cream">.env</code> file as{" "}
            <code className="rounded bg-panel-3 px-1.5 py-0.5 font-mono text-cream">{env}=…</code> and restart KINOVA
            (<code className="font-mono text-cream">docker compose up -d</code>).</p>
        </div>
      )}
    </section>
  );
}

export default function Settings() {
  const s = useQuery({ queryKey: ["status"], queryFn: api.status });
  return (
    <div className="mx-auto flex max-w-[1000px] flex-col gap-8">
      <PageHeader eyebrow="Settings" title="Connections &" accent="limits." />
      {s.isError && <ErrorState error={s.error} onRetry={() => s.refetch()} />}
      {s.isLoading || !s.data ? <Skeleton className="h-96" /> : (
        <>
          <p className="m-0 -mt-3 max-w-2xl text-[15px] leading-relaxed text-mute">
            Keys live only on your server, in the <code className="font-mono text-cream">.env</code> file — never in the browser.
            KINOVA tells you plainly whenever something runs without them.
          </p>
          <Integration name="Claude" on={s.data.integrations.claude.configured} env="ANTHROPIC_API_KEY"
            what="Picks the moments, plans each cut, and writes titles, captions and hashtags in your brand voice."
            extra={`Routine work: ${s.data.integrations.claude.models.fast} · Editing plans: ${s.data.integrations.claude.models.smart} · Cap $${s.data.limits.max_job_cost_usd.toFixed(2)} per production`}
            how={<p className="m-0">Create a key at <a href="https://platform.claude.com/" target="_blank" rel="noreferrer" className="font-semibold text-cream">platform.claude.com</a> → API Keys (it starts with <code className="font-mono text-cream">sk-ant-api</code>), and add a few dollars of credit.</p>}>
            {s.data.integrations.claude.configured && <ClaudeTest />}
          </Integration>
          <Integration name="Motion graphics" on={!!s.data.integrations.motion?.configured} env="MOTION_ENABLED"
            what="Animated word-by-word captions, hook titles, B-roll entrances and an on-screen call to action, rendered with Remotion in headless Chrome. Without it, cuts use the simpler FFmpeg look."
            extra={s.data.integrations.motion?.configured ? "Ready" : `Unavailable: ${s.data.integrations.motion?.detail ?? "unknown"}`}
            how={<p className="m-0">Rebuild KINOVA with <code className="font-mono text-cream">docker compose up --build</code>. If it still says unavailable, check that your computer could download headless Chrome during the build.</p>} />
          <Integration name="YouTube trends" on={s.data.integrations.youtube.configured} env="YOUTUBE_API_KEY"
            what="Looks up the most-viewed recent videos for your topic so every cut matches — or beats — what's working now. Free: 10,000 quota units a day (about 99 productions)."
            extra={`Region: ${s.data.integrations.youtube.region}`}
            how={<ol className="m-0 pl-5">
              <li>Open <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" className="font-semibold text-cream">console.cloud.google.com</a> and create a project.</li>
              <li>APIs &amp; Services → Library → enable <strong className="text-cream">YouTube Data API v3</strong>.</li>
              <li>Credentials → Create credentials → API key.</li>
            </ol>} />
          <Integration name="Pexels B-roll" on={!!s.data.integrations.pexels?.configured} env="PEXELS_API_KEY"
            what="Free stock footage for cutaways. The AI picks where a shot helps the story, KINOVA fetches a vertical clip and credits the creator. Free for commercial use; 200 searches an hour."
            how={<p className="m-0">Create a free account at <a href="https://www.pexels.com/api/" target="_blank" rel="noreferrer" className="font-semibold text-cream">pexels.com/api</a> and copy “Your API Key”.</p>} />
          <Integration name="Whisper (speech-to-text)" on={s.data.integrations.whisper.configured} env="WHISPER_ENABLED"
            what="Free, open-source transcription that runs on your own computer. The model downloads automatically the first time (about 150 MB for 'base')."
            extra={`Model: ${s.data.integrations.whisper.model}`}
            how={<p className="m-0">Set WHISPER_ENABLED=true.</p>} />
          <section className="card grid gap-6 p-6 sm:grid-cols-3">
            <div><span className="eyebrow">Upload limit</span><p className="serif-i m-0 mt-1 text-[36px]">{s.data.limits.max_upload_mb} MB</p></div>
            <div><span className="eyebrow">Video length</span><p className="serif-i m-0 mt-1 text-[36px]">{Math.round(s.data.limits.max_video_seconds / 60)} min</p></div>
            <div><span className="eyebrow">Worker</span><p className={`serif-i m-0 mt-1 text-[36px] ${s.data.worker.online ? "text-ok" : "text-danger"}`}>{s.data.worker.online ? "Online" : "Offline"}</p></div>
          </section>
          <section className="card flex flex-col gap-2 p-6">
            <span className="eyebrow">Workspace</span>
            <p className="m-0 text-[15px] text-mute">{s.data.organization.name} · {s.data.organization.plan} plan · local single-user mode. Team accounts, client workspaces and billing arrive in a later milestone.</p>
          </section>
        </>
      )}
    </div>
  );
}
