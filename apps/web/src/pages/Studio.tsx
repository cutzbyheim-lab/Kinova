import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Button, EmptyState, ErrorState, LinkButton, PageHeader, SectionHead, Skeleton, StatusChip, gradientFor } from "../components/ui";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";

export default function Studio() {
  const qc = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.projects() });
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.jobs(),
    refetchInterval: (q) => (q.state.data?.some((j) => j.status === "running" || j.status === "queued") ? 3000 : false),
  });
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");

  const create = useMutation({
    mutationFn: () => api.createProject({ name: name.trim(), topic: topic.trim() }),
    onSuccess: () => {
      setName(""); setTopic(""); setCreating(false);
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const archive = useMutation({
    mutationFn: (id: string) => api.updateProject(id, { status: "archived" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
  const projectName = (id: string) => projects.data?.find((p) => p.id === id)?.name ?? "Project";

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-10">
      <PageHeader eyebrow="Studio" title="The production" accent="floor.">
        <Button variant="ghost" icon={<Plus size={17} aria-hidden />} onClick={() => setCreating((c) => !c)}>New project</Button>
        <LinkButton to="/studio/new" variant="primary">New production</LinkButton>
      </PageHeader>

      {creating && (
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); if (name.trim()) create.mutate(); }}
          className="card grid gap-4 p-6 animate-rise md:grid-cols-[1fr_1fr_auto] md:items-end">
          <div>
            <label className="label" htmlFor="pname">Project name</label>
            <input id="pname" className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="Spring launch" required />
          </div>
          <div>
            <label className="label" htmlFor="ptopic">Topic <span className="font-normal text-dim">(used for trend research)</span></label>
            <input id="ptopic" className="field" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. skin fade tutorial" />
          </div>
          <Button type="submit" variant="cream" busy={create.isPending}>Create</Button>
          {create.isError && <div className="md:col-span-3"><ErrorState error={create.error} /></div>}
        </form>
      )}

      <section className="flex flex-col gap-5">
        <SectionHead num="01" title="Projects" />
        {projects.isError && <ErrorState error={projects.error} onRetry={() => projects.refetch()} />}
        {projects.isLoading ? (
          <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-72" />)}
          </div>
        ) : projects.data?.length ? (
          <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
            {projects.data.map((p, i) => (
              <article key={p.id} className="group card relative flex flex-col overflow-hidden animate-rise" style={{ animationDelay: `${i * 40}ms` }}>
                <Link to={`/studio/new?project=${p.id}`} className="relative block h-44 overflow-hidden no-underline" style={{ background: gradientFor(p.id) }}>
                  {p.cover_url && <img src={p.cover_url} alt="" className="h-full w-full object-cover opacity-80 transition-transform duration-500 group-hover:scale-105" />}
                  <span className="serif-i absolute left-4 top-3 text-[40px] leading-none text-cream/90 drop-shadow">{String(i + 1).padStart(2, "0")}</span>
                  {p.latest_job_status && <span className="absolute right-3 top-3"><StatusChip status={p.latest_job_status} /></span>}
                </Link>
                <div className="flex flex-1 flex-col gap-2 p-5">
                  <h3 className="m-0 text-[20px] font-bold tracking-tight">{p.name}</h3>
                  <p className="m-0 text-[14px] text-dim">{p.topic || "No topic yet"}</p>
                  <p className="m-0 mt-auto pt-2 text-[13px] text-faint">
                    {p.asset_count} upload{p.asset_count === 1 ? "" : "s"} · {p.output_count} clip{p.output_count === 1 ? "" : "s"} · updated {timeAgo(p.updated_at)}
                  </p>
                  <div className="flex gap-2 pt-2">
                    <LinkButton to={`/studio/new?project=${p.id}`} variant="cream" className="flex-1">Produce</LinkButton>
                    <Button aria-label={`Archive ${p.name}`} title="Archive" onClick={() => archive.mutate(p.id)} className="!px-3.5">
                      <Archive size={17} aria-hidden />
                    </Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="No projects yet." body="A project groups footage, productions and clips around one idea — a launch, a series, a client.">
            <Button variant="primary" onClick={() => setCreating(true)}>Create a project</Button>
          </EmptyState>
        )}
      </section>

      <section className="flex flex-col gap-4">
        <SectionHead num="02" title="Production log" />
        {jobs.isError && <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} />}
        {jobs.data?.length ? (
          <ul className="m-0 flex list-none flex-col p-0">
            {jobs.data.map((j) => (
              <li key={j.id}>
                <Link to={`/studio/jobs/${j.id}`}
                  className="flex flex-wrap items-center gap-4 border-b border-line py-4 no-underline transition-colors hover:bg-panel-2 sm:px-3">
                  <StatusChip status={j.status} />
                  <span className="min-w-0 flex-1 truncate text-[16px] font-semibold">{projectName(j.project_id)}
                    <span className="font-normal text-dim"> · {j.settings.platform} · {j.settings.variations} cuts</span></span>
                  <span className="text-[13px] text-dim">{j.planner === "heuristic" ? "Non-AI fallback" : j.planner === "claude" ? "Planned by Claude" : ""}</span>
                  <span className="font-mono text-[12px] text-faint">{timeAgo(j.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : !jobs.isLoading && <p className="m-0 text-[15px] text-mute">No productions yet. Start one and its whole history shows up here.</p>}
      </section>
    </div>
  );
}
