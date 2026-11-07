import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Film, UploadCloud } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, ErrorState, PageHeader, gradientFor } from "../components/ui";
import { api, uploadMedia } from "../lib/api";
import { fmtBytes, fmtDuration } from "../lib/format";
import type { Media } from "../lib/types";

const PLATFORMS = ["TikTok", "Instagram Reels", "YouTube Shorts"] as const;

function Step({ n, title, children, done }: { n: string; title: string; children: React.ReactNode; done?: boolean }) {
  return (
    <section className="card flex flex-col gap-5 p-6 sm:p-7 animate-rise">
      <div className="flex items-baseline gap-3">
        <span className={`serif-i text-[40px] leading-none ${done ? "text-orange" : "text-violet"}`}>{n}</span>
        <h2 className="m-0 text-[22px] font-bold">{title}</h2>
        {done && <CheckCircle2 size={20} className="ml-auto text-ok" aria-label="Done" />}
      </div>
      {children}
    </section>
  );
}

export default function NewProduction() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["status"], queryFn: api.status });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.projects() });
  const brands = useQuery({ queryKey: ["brands"], queryFn: api.brands });

  const [projectId, setProjectId] = useState(params.get("project") ?? "");
  const [newName, setNewName] = useState("");
  const [topic, setTopic] = useState("");
  const [goal, setGoal] = useState(params.get("goal") ?? "");
  const [platform, setPlatform] = useState<(typeof PLATFORMS)[number]>("TikTok");
  const [variations, setVariations] = useState(3);
  const [brandId, setBrandId] = useState("");
  const [asset, setAsset] = useState<Media | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // default project + brand
  useEffect(() => {
    if (!projectId && projects.data?.length) setProjectId(projects.data[0]!.id);
  }, [projects.data, projectId]);
  const project = projects.data?.find((p) => p.id === projectId);
  useEffect(() => {
    if (project) {
      setTopic((t) => t || project.topic);
      if (project.brand_id) setBrandId(project.brand_id);
    }
  }, [project]);
  useEffect(() => {
    if (!brandId && brands.data?.length) setBrandId(brands.data[0]!.id);
  }, [brands.data, brandId]);

  const footage = useQuery({
    queryKey: ["media", projectId],
    queryFn: () => api.media({ project_id: projectId, kind: "video" }),
    enabled: !!projectId,
  });

  const ensureProject = async () => {
    if (projectId) return projectId;
    const p = await api.createProject({ name: newName.trim() || "Untitled project", topic: topic.trim() });
    await qc.invalidateQueries({ queryKey: ["projects"] });
    setProjectId(p.id);
    return p.id;
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    const max = status.data?.limits.max_upload_mb ?? 1024;
    if (file.size > max * 1024 * 1024) {
      setUploadError(new Error(`That file is ${fmtBytes(file.size)} — the limit is ${max} MB.`));
      return;
    }
    setUploadError(null);
    setProgress(0);
    try {
      const pid = await ensureProject();
      const m = await uploadMedia(pid, file, setProgress);
      setAsset(m);
      qc.invalidateQueries({ queryKey: ["media", pid] });
    } catch (e) {
      setUploadError(e);
    } finally {
      setProgress(null);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    onFile(e.dataTransfer.files[0]);
  };

  const start = useMutation({
    mutationFn: async () => {
      const pid = await ensureProject();
      if (!asset) throw new Error("Upload or choose a video first.");
      return api.createJob(pid, {
        source_asset_id: asset.id, brand_id: brandId || null, topic: topic.trim(), goal: goal.trim(), platform, variations,
      });
    },
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      nav(`/studio/jobs/${job.id}`);
    },
  });

  const claudeOn = status.data?.integrations.claude.configured;
  const ytOn = status.data?.integrations.youtube.configured;

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-9">
      <PageHeader eyebrow="Studio — new production" title="Let's make" accent="something." />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-6">
          <Step n="01" title="Project" done={!!projectId}>
            {projects.data?.length ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="proj">Add to project</label>
                  <select id="proj" className="field" value={projectId} onChange={(e) => { setProjectId(e.target.value); setAsset(null); setTopic(""); }}>
                    {projects.data.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    <option value="">+ New project…</option>
                  </select>
                </div>
                {!projectId && (
                  <div>
                    <label className="label" htmlFor="newname">New project name</label>
                    <input id="newname" className="field" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Spring launch" />
                  </div>
                )}
              </div>
            ) : (
              <div>
                <label className="label" htmlFor="newname">Name your first project</label>
                <input id="newname" className="field" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Spring launch" />
              </div>
            )}
          </Step>

          <Step n="02" title="Footage" done={!!asset}>
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              className={`relative flex flex-col items-center justify-center gap-3 rounded-[18px] border-2 border-dashed px-6 py-12 text-center transition-colors duration-200 ${
                drag ? "border-orange bg-[#2a1810]" : "border-line-3 bg-ink-2"}`}
            >
              {progress !== null ? (
                <div className="flex w-full max-w-sm flex-col gap-3">
                  <span className="serif-i text-[44px] leading-none text-orange">{progress}%</span>
                  <div className="h-2 overflow-hidden rounded-full bg-line-2">
                    <div className="h-full rounded-full bg-orange transition-[width] duration-300" style={{ width: `${progress}%` }} />
                  </div>
                  <span className="text-[14px] text-dim">{progress < 100 ? "Uploading…" : "Checking the file and making a thumbnail…"}</span>
                </div>
              ) : (
                <>
                  <UploadCloud size={36} className="text-orange" aria-hidden />
                  <p className="m-0 text-[20px] font-semibold">Drop a video here</p>
                  <p className="m-0 text-[14px] text-dim">
                    MP4, MOV, WEBM or MKV · up to {Math.round((status.data?.limits.max_video_seconds ?? 900) / 60)} min · {status.data?.limits.max_upload_mb ?? 1024} MB
                  </p>
                  <Button variant="cream" onClick={() => fileRef.current?.click()}>Choose file</Button>
                  <input ref={fileRef} type="file" accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mkv,.m4v"
                    className="sr-only" aria-label="Choose video file" onChange={(e) => onFile(e.target.files?.[0])} />
                </>
              )}
            </div>
            {uploadError != null && <ErrorState error={uploadError} />}

            {footage.data && footage.data.length > 0 && (
              <div className="flex flex-col gap-3">
                <span className="label !mb-0">Or pick footage already in this project</span>
                <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(170px,1fr))]">
                  {footage.data.map((m) => (
                    <button key={m.id} type="button" onClick={() => setAsset(m)} aria-pressed={asset?.id === m.id}
                      className={`overflow-hidden rounded-2xl border-2 bg-panel-2 p-0 text-left transition-colors ${asset?.id === m.id ? "border-orange" : "border-transparent hover:border-line-3"}`}>
                      <div className="relative aspect-video" style={{ background: gradientFor(m.id) }}>
                        {m.thumbnail_url ? <img src={m.thumbnail_url} alt="" className="h-full w-full object-cover" /> : <Film className="m-auto mt-8 text-dim" aria-hidden />}
                        <span className="absolute bottom-1.5 right-1.5 rounded bg-ink/85 px-1.5 font-mono text-[11px]">{fmtDuration(m.duration_s)}</span>
                      </div>
                      <span className="block truncate px-3 py-2 text-[13px] font-semibold text-cream">{m.filename}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Step>

          <Step n="03" title="Brief">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="topic">Topic <span className="font-normal text-dim">— KINOVA researches trends for this</span></label>
                <input id="topic" className="field" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. skin fade tutorial" />
              </div>
              <div>
                <label className="label" htmlFor="brand">Brand</label>
                <select id="brand" className="field" value={brandId} onChange={(e) => setBrandId(e.target.value)}>
                  <option value="">No brand</option>
                  {brands.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="label" htmlFor="goal">Goal</label>
              <textarea id="goal" className="field min-h-24 resize-y" value={goal} onChange={(e) => setGoal(e.target.value)}
                placeholder="What should these clips achieve? e.g. get more bookings from new local clients" />
            </div>
            <div className="flex flex-wrap gap-8">
              <fieldset className="m-0 border-0 p-0">
                <legend className="label">Platform</legend>
                <div className="flex flex-wrap gap-2">
                  {PLATFORMS.map((p) => (
                    <button key={p} type="button" onClick={() => setPlatform(p)} aria-pressed={platform === p}
                      className={`min-h-11 rounded-full border px-4 text-[14px] font-semibold transition-colors ${platform === p ? "border-cream bg-cream text-ink" : "border-line-3 text-mute hover:border-cream"}`}>
                      {p}
                    </button>
                  ))}
                </div>
              </fieldset>
              <fieldset className="m-0 border-0 p-0">
                <legend className="label">Variations</legend>
                <div className="flex gap-2">
                  {[1, 2, 3].map((n) => (
                    <button key={n} type="button" onClick={() => setVariations(n)} aria-pressed={variations === n}
                      className={`h-11 w-11 rounded-full border text-[15px] font-bold transition-colors ${variations === n ? "border-orange bg-orange text-ink" : "border-line-3 text-mute hover:border-cream"}`}>
                      {n}
                    </button>
                  ))}
                </div>
              </fieldset>
            </div>
          </Step>

          {start.isError && <ErrorState error={start.error} />}
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="primary" className="min-h-14 px-8 text-[17px]" busy={start.isPending} disabled={!asset || progress !== null}
              onClick={() => start.mutate()}>
              Start production →
            </Button>
            {!asset && <span className="text-[14px] text-dim">Add footage to start.</span>}
          </div>
        </div>

        <aside className="flex flex-col gap-5 lg:sticky lg:top-7">
          <div className="card flex flex-col gap-4 p-6">
            <span className="eyebrow">What happens next</span>
            <ol className="m-0 flex list-none flex-col gap-3 p-0 text-[14px] leading-snug text-mute">
              <li><strong className="text-cream">Transcribe</strong> — {status.data?.integrations.whisper.configured
                ? "free open-source Whisper, on your machine." : <span className="text-warn">skipped: Whisper is turned off.</span>}</li>
              <li><strong className="text-cream">Trends</strong> — {ytOn ? "top YouTube videos for your topic, last 30 days." : <span className="text-warn">skipped: YouTube not connected.</span>}</li>
              <li><strong className="text-cream">Moments</strong> — {claudeOn ? "Claude picks the strongest cuts for each style." : <span className="text-warn">non-AI fallback: Claude not connected.</span>}</li>
              <li><strong className="text-cream">Render</strong> — 9:16 with burned-in captions and your brand color.</li>
              <li><strong className="text-cream">Check & copy</strong> — automatic QC, then titles, captions and hashtags{claudeOn ? "." : <span className="text-warn"> (needs Claude).</span>}</li>
            </ol>
          </div>
          <div className="card flex flex-col gap-2 p-6">
            <span className="eyebrow">Cost guard</span>
            <p className="m-0 text-[14px] leading-snug text-mute">
              Each production stops calling Claude once it would pass <strong className="text-cream">${status.data?.limits.max_job_cost_usd.toFixed(2) ?? "0.50"}</strong>.
              Transcription and rendering are free.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
