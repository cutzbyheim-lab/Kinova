import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Film, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import ClipTile from "../components/ClipTile";
import { Button, EmptyState, ErrorState, LinkButton, PageHeader, Skeleton, gradientFor } from "../components/ui";
import { api } from "../lib/api";
import { fmtBytes, fmtDuration, timeAgo } from "../lib/format";

type Tab = "clips" | "uploads";

export default function Library() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("clips");
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
          {(["clips", "uploads"] as Tab[]).map((t) => (
            <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`min-h-10 rounded-full px-5 text-[14px] font-semibold capitalize transition-colors ${tab === t ? "bg-cream text-ink" : "text-mute hover:text-cream"}`}>
              {t === "clips" ? `Generated clips${outputs.data ? ` · ${outputs.data.length}` : ""}` : `Uploads${media.data ? ` · ${media.data.length}` : ""}`}
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

      {tab === "clips" ? (
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
