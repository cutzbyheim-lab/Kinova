import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Film, Music2, UploadCloud, X } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button, ErrorState, PageHeader, gradientFor } from "../components/ui";
import { api, uploadMedia } from "../lib/api";
import { fmtBytes, fmtDuration } from "../lib/format";
import type { Media } from "../lib/types";

const PLATFORMS = ["TikTok", "Instagram Reels", "YouTube Shorts"] as const;
const MAX_CLIPS = 8;

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

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={`relative h-8 w-14 shrink-0 rounded-full transition-colors duration-200 ${on ? "bg-orange" : "bg-line-3"}`}>
      <span className={`absolute top-1 h-6 w-6 rounded-full bg-cream transition-[left] duration-200 ${on ? "left-7" : "left-1"}`} />
    </button>
  );
}

export default function NewProduction() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["status"], queryFn: api.status });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.projects() });
  const brands = useQuery({ queryKey: ["brands"], queryFn: api.brands });
  const music = useQuery({ queryKey: ["music"], queryFn: api.music });

  const [projectId, setProjectId] = useState(params.get("project") ?? "");
  const [newName, setNewName] = useState("");
  const [topic, setTopic] = useState("");
  const [goal, setGoal] = useState(params.get("goal") ?? "");
  const [platform, setPlatform] = useState<(typeof PLATFORMS)[number]>("TikTok");
  const [variations, setVariations] = useState(3);
  const [brandId, setBrandId] = useState("");
  const [selected, setSelected] = useState<Media[]>([]);
  const [musicChoice, setMusicChoice] = useState("auto");
  const [broll, setBroll] = useState(true);
  const [uploading, setUploading] = useState<{ name: string; pct: number; index: number; total: number } | null>(null);
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

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

  const toggle = (m: Media) =>
    setSelected((s) => (s.some((x) => x.id === m.id) ? s.filter((x) => x.id !== m.id) : s.length < MAX_CLIPS ? [...s, m] : s));

  const onFiles = async (files: FileList | File[] | null | undefined) => {
    const list = Array.from(files ?? []).slice(0, MAX_CLIPS - selected.length);
    if (!list.length) return;
    const max = status.data?.limits.max_upload_mb ?? 1024;
    const tooBig = list.find((f) => f.size > max * 1024 * 1024);
    if (tooBig) {
      setUploadError(new Error(`${tooBig.name} is ${fmtBytes(tooBig.size)} — the limit is ${max} MB.`));
      return;
    }
    setUploadError(null);
    try {
      const pid = await ensureProject();
      for (const [i, file] of list.entries()) {
        setUploading({ name: file.name, pct: 0, index: i + 1, total: list.length });
        const m = await uploadMedia(pid, file, (pct) => setUploading({ name: file.name, pct, index: i + 1, total: list.length }));
        setSelected((s) => [...s, m]);
      }
      qc.invalidateQueries({ queryKey: ["media", pid] });
    } catch (e) {
      setUploadError(e);
    } finally {
      setUploading(null);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    onFiles(e.dataTransfer.files);
  };

  const start = useMutation({
    mutationFn: async () => {
      const pid = await ensureProject();
      if (!selected.length) throw new Error("Upload or choose at least one video first.");
      return api.createJob(pid, {
        source_asset_ids: selected.map((m) => m.id), brand_id: brandId || null, topic: topic.trim(),
        goal: goal.trim(), platform, variations, music: musicChoice, broll,
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
  const pexelsOn = status.data?.integrations.pexels?.configured;
  const totalSecs = selected.reduce((t, m) => t + (m.duration_s ?? 0), 0);

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
                  <select id="proj" className="field" value={projectId} onChange={(e) => { setProjectId(e.target.value); setSelected([]); setTopic(""); }}>
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

          <Step n="02" title="Footage" done={selected.length > 0}>
            <p className="m-0 -mt-2 text-[14px] text-dim">Add one video or up to {MAX_CLIPS}. With several, KINOVA builds each cut from the best moments across all of them.</p>
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              className={`relative flex flex-col items-center justify-center gap-3 rounded-[18px] border-2 border-dashed px-6 py-10 text-center transition-colors duration-200 ${
                drag ? "border-orange bg-[#2a1810]" : "border-line-3 bg-ink-2"}`}
            >
              {uploading ? (
                <div className="flex w-full max-w-sm flex-col gap-3">
                  <span className="serif-i text-[44px] leading-none text-orange">{uploading.pct}%</span>
                  <div className="h-2 overflow-hidden rounded-full bg-line-2">
                    <div className="h-full rounded-full bg-orange transition-[width] duration-300" style={{ width: `${uploading.pct}%` }} />
                  </div>
                  <span className="truncate text-[14px] text-dim">
                    {uploading.total > 1 && `${uploading.index} of ${uploading.total} · `}
                    {uploading.pct < 100 ? `Uploading ${uploading.name}…` : "Checking the file…"}
                  </span>
                </div>
              ) : (
                <>
                  <UploadCloud size={36} className="text-orange" aria-hidden />
                  <p className="m-0 text-[20px] font-semibold">Drop videos here</p>
                  <p className="m-0 text-[14px] text-dim">
                    MP4, MOV, WEBM or MKV · up to {Math.round((status.data?.limits.max_video_seconds ?? 900) / 60)} min each
                  </p>
                  <Button variant="cream" onClick={() => fileRef.current?.click()} disabled={selected.length >= MAX_CLIPS}>Choose files</Button>
                  <input ref={fileRef} type="file" multiple accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mkv,.m4v"
                    className="sr-only" aria-label="Choose video files" onChange={(e) => { onFiles(e.target.files); e.target.value = ""; }} />
                </>
              )}
            </div>
            {uploadError != null && <ErrorState error={uploadError} />}

            {selected.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="label !mb-0">In this production · {selected.length} clip{selected.length === 1 ? "" : "s"} · {fmtDuration(totalSecs)}</span>
                <ol className="m-0 flex list-none flex-wrap gap-2 p-0">
                  {selected.map((m, i) => (
                    <li key={m.id} className="flex items-center gap-2 rounded-full border border-orange/60 bg-[#2a1810] py-1 pl-3 pr-1 text-[13px]">
                      <span className="serif-i text-[17px] text-orange">{i + 1}</span>
                      <span className="max-w-[180px] truncate font-semibold">{m.filename}</span>
                      <span className="font-mono text-[11px] text-dim">{fmtDuration(m.duration_s)}</span>
                      <button type="button" onClick={() => toggle(m)} aria-label={`Remove ${m.filename}`}
                        className="flex h-8 w-8 items-center justify-center rounded-full text-dim hover:text-cream"><X size={14} /></button>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {footage.data && footage.data.length > 0 && (
              <div className="flex flex-col gap-3">
                <span className="label !mb-0">Footage already in this project — click to add</span>
                <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(170px,1fr))]">
                  {footage.data.map((m) => {
                    const pos = selected.findIndex((x) => x.id === m.id);
                    return (
                      <button key={m.id} type="button" onClick={() => toggle(m)} aria-pressed={pos >= 0}
                        className={`relative overflow-hidden rounded-2xl border-2 bg-panel-2 p-0 text-left transition-colors ${pos >= 0 ? "border-orange" : "border-transparent hover:border-line-3"}`}>
                        <div className="relative aspect-video" style={{ background: gradientFor(m.id) }}>
                          {m.thumbnail_url ? <img src={m.thumbnail_url} alt="" className="h-full w-full object-cover" /> : <Film className="m-auto mt-8 text-dim" aria-hidden />}
                          <span className="absolute bottom-1.5 right-1.5 rounded bg-ink/85 px-1.5 font-mono text-[11px]">{fmtDuration(m.duration_s)}</span>
                          {pos >= 0 && <span className="absolute left-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-orange text-[13px] font-bold text-ink">{pos + 1}</span>}
                        </div>
                        <span className="block truncate px-3 py-2 text-[13px] font-semibold text-cream">{m.filename}</span>
                      </button>
                    );
                  })}
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

          <Step n="04" title="Sound & B-roll">
            <div>
              <label className="label" htmlFor="music">Background music</label>
              <select id="music" className="field" value={musicChoice} onChange={(e) => setMusicChoice(e.target.value)}>
                <option value="auto">Let the AI pick from my music library{music.data ? ` (${music.data.length} track${music.data.length === 1 ? "" : "s"})` : ""}</option>
                <option value="none">No music</option>
                {music.data?.map((m) => <option key={m.id} value={m.id}>{m.meta.title ?? m.filename}{m.meta.mood ? ` — ${m.meta.mood}` : ""}</option>)}
              </select>
              <p className="mb-0 mt-2 flex items-center gap-2 text-[13px] text-dim">
                <Music2 size={14} aria-hidden />
                {music.data?.length ? "Music sits under the voice and dips automatically when someone talks." :
                  <>Your library is empty — <Link to="/library?tab=music" className="font-semibold text-cream">add tracks you're allowed to use</Link>.</>}
              </p>
            </div>
            <div className="flex items-start gap-4 rounded-2xl bg-panel-2 p-4">
              <Toggle on={broll} onChange={setBroll} label="Add stock B-roll" />
              <div className="flex flex-col gap-1">
                <span className="text-[15px] font-semibold">Add stock B-roll</span>
                <span className="text-[13px] leading-snug text-dim">
                  {pexelsOn ? "The AI drops in short cutaways from Pexels (free for commercial use) where they help the story; your audio keeps playing."
                    : <>Needs a free Pexels key — <Link to="/settings" className="font-semibold text-cream">connect in Settings</Link>. Without it, cuts use only your footage.</>}
                </span>
              </div>
            </div>
          </Step>

          {start.isError && <ErrorState error={start.error} />}
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="primary" className="min-h-14 px-8 text-[17px]" busy={start.isPending} disabled={!selected.length || !!uploading}
              onClick={() => start.mutate()}>
              Start production →
            </Button>
            {!selected.length && <span className="text-[14px] text-dim">Add footage to start.</span>}
          </div>
        </div>

        <aside className="flex flex-col gap-5 lg:sticky lg:top-7">
          <div className="card flex flex-col gap-4 p-6">
            <span className="eyebrow">What happens next</span>
            <ol className="m-0 flex list-none flex-col gap-3 p-0 text-[14px] leading-snug text-mute">
              <li><strong className="text-cream">Transcribe</strong> — {status.data?.integrations.whisper.configured
                ? "free open-source Whisper, on your machine." : <span className="text-warn">skipped: Whisper is turned off.</span>}</li>
              <li><strong className="text-cream">Trends</strong> — {ytOn ? "top YouTube videos for your topic, last 30 days." : <span className="text-warn">skipped: YouTube not connected.</span>}</li>
              <li><strong className="text-cream">Moments</strong> — {claudeOn ? "Claude picks the strongest cuts across every clip." : <span className="text-warn">non-AI fallback: Claude not connected.</span>}</li>
              <li><strong className="text-cream">B-roll & music</strong> — {pexelsOn ? "stock cutaways from Pexels, music from your library." : "music from your library; B-roll needs Pexels."}</li>
              <li><strong className="text-cream">Render</strong> — 9:16 with burned-in captions and your brand color.</li>
              <li><strong className="text-cream">Check & copy</strong> — automatic QC, then titles, captions and hashtags{claudeOn ? "." : <span className="text-warn"> (needs Claude).</span>}</li>
            </ol>
          </div>
          <div className="card flex flex-col gap-2 p-6">
            <span className="eyebrow">Cost guard</span>
            <p className="m-0 text-[14px] leading-snug text-mute">
              Each production stops calling Claude once it would pass <strong className="text-cream">${status.data?.limits.max_job_cost_usd.toFixed(2) ?? "0.50"}</strong>.
              Transcription, B-roll and rendering are free.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
