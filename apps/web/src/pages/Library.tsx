import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Film, Music2, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import ClipTile from "../components/ClipTile";
import { Button, EmptyState, ErrorState, LinkButton, PageHeader, Skeleton, gradientFor } from "../components/ui";
import { api, uploadMusic } from "../lib/api";
import { fmtBytes, fmtDuration, timeAgo } from "../lib/format";

type Tab = "clips" | "uploads" | "music";

function MusicPanel() {
  const qc = useQueryClient();
  const tracks = useQuery({ queryKey: ["music"], queryFn: api.music });
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [mood, setMood] = useState("");
  const add = useMutation({
    mutationFn: () => uploadMusic(file!, title.trim(), mood.trim()),
    onSuccess: () => { setFile(null); setTitle(""); setMood(""); qc.invalidateQueries({ queryKey: ["music"] }); },
  });
  const del = useMutation({ mutationFn: api.deleteMedia, onSuccess: () => qc.invalidateQueries({ queryKey: ["music"] }) });

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={(e) => { e.preventDefault(); if (file) add.mutate(); }} className="card grid gap-4 p-6 md:grid-cols-[1.2fr_1fr_1fr_auto] md:items-end">
        <div>
          <label className="label" htmlFor="mfile">Track</label>
          <input id="mfile" type="file" accept=".mp3,.wav,.m4a,.aac,.ogg,.flac,audio/*" className="field !py-2.5 text-[14px] file:mr-3 file:rounded-full file:border-0 file:bg-cream file:px-3 file:py-1 file:font-semibold file:text-ink"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
        </div>
        <div>
          <label className="label" htmlFor="mtitle">Title</label>
          <input id="mtitle" className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to file name" />
        </div>
        <div>
          <label className="label" htmlFor="mmood">Mood <span className="font-normal text-dim">— helps the AI pick</span></label>
          <input id="mmood" className="field" value={mood} onChange={(e) => setMood(e.target.value)} placeholder="e.g. upbeat hip-hop, chill lo-fi" />
        </div>
        <Button type="submit" variant="primary" busy={add.isPending} disabled={!file}>Add track</Button>
        {add.isError && <div className="md:col-span-4"><ErrorState error={add.error} /></div>}
      </form>
      <p className="m-0 -mt-2 max-w-3xl text-[14px] leading-relaxed text-dim">
        Only add music you have the rights to use in posted videos — for example tracks from YouTube Studio's Audio Library,
        or a licensing subscription. For trending TikTok or Reels sounds, add them in the app when you post.
      </p>
      {tracks.isError && <ErrorState error={tracks.error} onRetry={() => tracks.refetch()} />}
      {tracks.data?.length ? (
        <ul className="m-0 flex list-none flex-col p-0">
          {tracks.data.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-4 border-b border-line py-3">
              <Music2 size={18} className="text-orange" aria-hidden />
              <div className="min-w-[160px] flex-1">
                <p className="m-0 text-[15px] font-bold">{t.meta.title ?? t.filename}</p>
                <p className="m-0 text-[12px] text-dim">{t.meta.mood || "No mood set"} · {fmtDuration(t.duration_s)}</p>
              </div>
              {t.url && <audio controls preload="none" src={t.url} className="h-10 max-w-full" aria-label={`Preview ${t.meta.title ?? t.filename}`} />}
              <Button aria-label={`Delete ${t.meta.title ?? t.filename}`} className="!px-3"
                onClick={() => { if (confirm("Delete this track from your music library?")) del.mutate(t.id); }}>
                <Trash2 size={16} aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      ) : !tracks.isLoading && (
        <EmptyState title="No music yet." body="Add a few tracks with a mood each. The AI picks the best fit for every cut and lowers it automatically under the voice." />
      )}
    </div>
  );
}

export default function Library() {
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>((params.get("tab") as Tab) || "clips");
  const [q, setQ] = useState("");
  const [projectId, setProjectId] = useState("");
  const [approvedOnly, setApprovedOnly] = useState(false);
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.projects() });
  const outputs = useQuery({ queryKey: ["outputs", projectId], queryFn: () => api.outputs(projectId || undefined) });
  const media = useQuery({ queryKey: ["media-lib", projectId, q], queryFn: () => api.media({ project_id: projectId, q }) });
  const del = useMutation({
    mutationFn: api.deleteMedia,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["media-lib"] }),
  });

  const needle = q.trim().toLowerCase();
  const clips = (outputs.data ?? []).filter((o) =>
    (!approvedOnly || o.approved) &&
    (!needle || `${o.title} ${o.caption} ${o.style} ${o.hashtags.join(" ")}`.toLowerCase().includes(needle)));
  const pname = (id: string | null) => projects.data?.find((p) => p.id === id)?.name ?? "";

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-8">
      <PageHeader eyebrow="Content library" title="Everything," accent="filed." />

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Library sections" className="flex rounded-full border border-line-2 p-1">
          {(["clips", "uploads", "music"] as Tab[]).map((t) => (
            <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`min-h-10 rounded-full px-5 text-[14px] font-semibold capitalize transition-colors ${tab === t ? "bg-cream text-ink" : "text-mute hover:text-cream"}`}>
              {t === "clips" ? `Generated clips${outputs.data ? ` · ${outputs.data.length}` : ""}` : t === "uploads" ? `Uploads${media.data ? ` · ${media.data.length}` : ""}` : "Music"}
            </button>
          ))}
        </div>
        <div className="relative min-w-[220px] flex-1">
          <Search size={17} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-dim" aria-hidden />
          <label htmlFor="libq" className="sr-only">Search</label>
          <input id="libq" className="field !rounded-full !pl-11" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles, captions, files…" />
        </div>
        <label htmlFor="libp" className="sr-only">Project</label>
        <select id="libp" className="field !w-auto !rounded-full" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          <option value="">All projects</option>
          {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {tab === "clips" && (
          <label className="flex min-h-11 cursor-pointer items-center gap-2 text-[14px] text-mute">
            <input type="checkbox" checked={approvedOnly} onChange={(e) => setApprovedOnly(e.target.checked)} className="h-4 w-4 accent-orange" />
            Approved only
          </label>
        )}
      </div>

      {tab === "music" ? <MusicPanel /> : tab === "clips" ? (
        outputs.isError ? <ErrorState error={outputs.error} onRetry={() => outputs.refetch()} /> :
        outputs.isLoading ? (
          <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(170px,1fr))]">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="aspect-[9/16]" />)}</div>
        ) : clips.length ? (
          <div className="grid gap-x-4 gap-y-6 [grid-template-columns:repeat(auto-fill,minmax(170px,1fr))]">
            {clips.map((o) => <ClipTile key={o.id} o={o} to={`/studio/jobs/${o.job_id}`} />)}
          </div>
        ) : (
          <EmptyState title={outputs.data?.length ? "Nothing matches." : "No clips yet."}
            body={outputs.data?.length ? "Try a different search or project." : "Finished, quality-checked cuts from every production land here."}>
            {!outputs.data?.length && <LinkButton to="/studio/new" variant="primary">Start a production</LinkButton>}
          </EmptyState>
        )
      ) : media.isError ? <ErrorState error={media.error} onRetry={() => media.refetch()} /> : media.data?.length ? (
        <ul className="m-0 grid list-none gap-4 p-0 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
          {media.data.map((m) => (
            <li key={m.id} className="card overflow-hidden">
              <div className="relative aspect-video" style={{ background: gradientFor(m.id) }}>
                {m.thumbnail_url ? <img src={m.thumbnail_url} alt="" className="h-full w-full object-cover" /> : <Film className="m-auto mt-12 text-dim" aria-hidden />}
                {m.duration_s != null && <span className="absolute bottom-2 right-2 rounded bg-ink/85 px-1.5 font-mono text-[11px]">{fmtDuration(m.duration_s)}</span>}
                <span className="absolute left-2 top-2 rounded-full bg-cream px-2 py-0.5 text-[11px] font-bold text-ink">Original</span>
              </div>
              <div className="flex items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <p className="m-0 truncate text-[14px] font-bold">{m.filename}</p>
                  <p className="m-0 text-[12px] text-dim">{pname(m.project_id)} · {fmtBytes(m.size_bytes)} · {m.width}×{m.height} · {timeAgo(m.created_at)}</p>
                </div>
                <Button aria-label={`Delete ${m.filename}`} title="Delete original" className="!px-3"
                  onClick={() => { if (confirm(`Delete ${m.filename}? Productions made from it will also be removed. This can't be undone.`)) del.mutate(m.id); }}>
                  <Trash2 size={16} aria-hidden />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : !media.isLoading && (
        <EmptyState title="No uploads yet." body="Original footage is stored privately and never modified — every clip is rendered from a copy.">
          <LinkButton to="/studio/new" variant="primary">Upload footage</LinkButton>
        </EmptyState>
      )}
    </div>
  );
}
