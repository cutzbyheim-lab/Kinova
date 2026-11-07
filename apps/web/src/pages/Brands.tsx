import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, EmptyState, ErrorState, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import type { Brand, BrandInput } from "../lib/types";

const EMPTY: BrandInput = {
  name: "", industry: "", audience: "", voice: "", personality: "", products: "", goals: "",
  editing_style: "", instructions: "", colors: ["#FF6A2B", "#9A80FF"], fonts: [],
};

const FIELDS: { key: keyof BrandInput; label: string; hint: string; long?: boolean }[] = [
  { key: "industry", label: "Industry", hint: "e.g. Barbershop, fitness coaching, SaaS" },
  { key: "audience", label: "Audience", hint: "Who you're talking to", long: true },
  { key: "voice", label: "Voice", hint: "How you sound — e.g. direct, warm, a little cocky", long: true },
  { key: "personality", label: "Personality", hint: "Three or four adjectives", long: true },
  { key: "products", label: "Products & services", hint: "What you sell", long: true },
  { key: "goals", label: "Marketing goals", hint: "e.g. more bookings, grow followers", long: true },
  { key: "editing_style", label: "Editing style", hint: "e.g. fast cuts, bold captions, no music", long: true },
  { key: "instructions", label: "Always / never", hint: "Rules for the AI — e.g. never use slang, always mention the city", long: true },
];

function BrandEditor({ brand, onDone }: { brand: Brand | null; onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<BrandInput>(brand ? { ...EMPTY, ...brand } : EMPTY);
  useEffect(() => setForm(brand ? { ...EMPTY, ...brand } : EMPTY), [brand]);
  const set = <K extends keyof BrandInput>(k: K, v: BrandInput[K]) => setForm((f) => ({ ...f, [k]: v }));

  const save = useMutation({
    mutationFn: () => {
      const { name, industry, audience, voice, personality, products, goals, editing_style, instructions, colors, fonts } = form;
      const body = { name, industry, audience, voice, personality, products, goals, editing_style, instructions, colors, fonts };
      return brand ? api.updateBrand(brand.id, body) : api.createBrand(body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["brands"] }); qc.invalidateQueries({ queryKey: ["overview"] }); onDone(); },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteBrand(brand!.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["brands"] }); onDone(); },
  });

  return (
    <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="card flex flex-col gap-6 p-6 sm:p-8 animate-rise">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-[240px] flex-1">
          <label className="label" htmlFor="bname">Brand name</label>
          <input id="bname" className="field !text-[22px] !font-bold" value={form.name} onChange={(e) => set("name", e.target.value)} required placeholder="Your brand" />
        </div>
      </div>

      <fieldset className="m-0 border-0 p-0">
        <legend className="label">Colors <span className="font-normal text-dim">— the first one is used for on-screen hooks</span></legend>
        <div className="flex flex-wrap items-center gap-3">
          {form.colors.map((c, i) => (
            <div key={i} className="flex items-center gap-2 rounded-full border border-line-2 bg-panel-2 py-1 pl-1 pr-2">
              <input type="color" value={c} aria-label={`Color ${i + 1}`}
                onChange={(e) => set("colors", form.colors.map((x, k) => (k === i ? e.target.value.toUpperCase() : x)))}
                className="h-9 w-9 cursor-pointer rounded-full border-0 bg-transparent p-0" />
              <span className="font-mono text-[13px]">{c.toUpperCase()}</span>
              <button type="button" aria-label={`Remove color ${c}`} onClick={() => set("colors", form.colors.filter((_, k) => k !== i))}
                className="flex h-7 w-7 items-center justify-center rounded-full text-dim hover:text-cream"><X size={14} /></button>
            </div>
          ))}
          {form.colors.length < 8 && (
            <Button className="!min-h-10" icon={<Plus size={15} aria-hidden />} onClick={() => set("colors", [...form.colors, "#F4EDE4"])}>Add</Button>
          )}
        </div>
      </fieldset>

      <div className="grid gap-5 md:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.key} className={f.key === "instructions" ? "md:col-span-2" : ""}>
            <label className="label" htmlFor={`b-${f.key}`}>{f.label}</label>
            {f.long ? (
              <textarea id={`b-${f.key}`} className="field min-h-20 resize-y" value={form[f.key] as string}
                onChange={(e) => set(f.key, e.target.value as never)} placeholder={f.hint} />
            ) : (
              <input id={`b-${f.key}`} className="field" value={form[f.key] as string} onChange={(e) => set(f.key, e.target.value as never)} placeholder={f.hint} />
            )}
          </div>
        ))}
      </div>

      {(save.isError || remove.isError) && <ErrorState error={save.error ?? remove.error} />}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" variant="primary" busy={save.isPending}>{brand ? "Save brand" : "Create brand"}</Button>
        <Button onClick={onDone}>Cancel</Button>
        {brand && (
          <Button variant="danger" className="ml-auto" icon={<Trash2 size={16} aria-hidden />} busy={remove.isPending}
            onClick={() => confirm(`Delete ${brand.name}? Projects using it keep their clips.`) && remove.mutate()}>Delete</Button>
        )}
      </div>
    </form>
  );
}

export default function Brands() {
  const brands = useQuery({ queryKey: ["brands"], queryFn: api.brands });
  const [editing, setEditing] = useState<Brand | "new" | null>(null);

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-8">
      <PageHeader eyebrow="Brand brain" title="Teach it" accent="once.">
        {editing === null && <Button variant="primary" icon={<Plus size={17} aria-hidden />} onClick={() => setEditing("new")}>New brand</Button>}
      </PageHeader>
      <p className="m-0 -mt-3 max-w-2xl text-[17px] leading-relaxed text-mute">
        Every editing plan and caption reads this profile — your colors go on screen, your voice goes in the copy.
      </p>

      {editing !== null && <BrandEditor brand={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}

      {brands.isError && <ErrorState error={brands.error} onRetry={() => brands.refetch()} />}
      {brands.isLoading ? <Skeleton className="h-40" /> : brands.data?.length ? (
        <ul className="m-0 grid list-none gap-5 p-0 md:grid-cols-2">
          {brands.data.map((b, i) => (
            <li key={b.id}>
              <button type="button" onClick={() => setEditing(b)}
                className="card group flex w-full flex-col gap-4 p-6 text-left transition-colors hover:border-line-3">
                <div className="flex h-20 overflow-hidden rounded-2xl">
                  {(b.colors.length ? b.colors : ["#3A302B"]).map((c, k) => <div key={k} className="flex-1" style={{ background: c }} />)}
                </div>
                <div className="flex items-baseline gap-3">
                  <span className="serif-i text-[34px] leading-none text-violet">{String(i + 1).padStart(2, "0")}</span>
                  <span className="text-[24px] font-bold tracking-tight text-cream">{b.name}</span>
                </div>
                <span className="text-[14px] leading-relaxed text-mute">{b.voice || b.industry || "Add a voice and audience so the AI sounds like you."}</span>
                <span className="text-[14px] font-bold text-cream group-hover:text-orange">Edit →</span>
              </button>
            </li>
          ))}
        </ul>
      ) : editing === null && (
        <EmptyState title="No brand yet." body="Add your name, colors and how you talk. It takes two minutes and every production gets better.">
          <Button variant="primary" onClick={() => setEditing("new")}>Create your brand</Button>
        </EmptyState>
      )}
    </div>
  );
}
