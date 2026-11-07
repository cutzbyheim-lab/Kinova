import { PageHeader, LinkButton } from "../components/ui";

interface Props {
  eyebrow: string;
  title: string;
  accent: string;
  pitch: string;
  points: string[];
  note?: string;
}

/** Honest placeholder for sections on the roadmap: says what's coming, never shows fake data. */
export default function Coming({ eyebrow, title, accent, pitch, points, note }: Props) {
  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-10">
      <PageHeader eyebrow={eyebrow} title={title} accent={accent} />
      <section className="relative overflow-hidden rounded-[var(--radius-card)] border border-line bg-panel p-8 sm:p-12">
        <div aria-hidden className="pointer-events-none absolute -bottom-24 -right-16 h-80 w-80 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(154,128,255,.28), transparent 65%)" }} />
        <div className="relative flex max-w-2xl flex-col gap-6">
          <span className="inline-flex w-fit rounded-full border border-violet/60 px-3 py-1 text-[13px] font-bold text-violet">In production · next milestones</span>
          <p className="m-0 text-[clamp(24px,3vw,34px)] font-semibold leading-tight">{pitch}</p>
          <ol className="m-0 flex list-none flex-col gap-3 p-0">
            {points.map((p, i) => (
              <li key={i} className="flex items-baseline gap-4 border-b border-line py-2">
                <span className="serif-i w-8 shrink-0 text-[26px] text-violet">{String(i + 1).padStart(2, "0")}</span>
                <span className="text-[16px] text-mute">{p}</span>
              </li>
            ))}
          </ol>
          {note && <p className="m-0 text-[14px] text-dim">{note}</p>}
          <div className="flex flex-wrap gap-3"><LinkButton to="/studio/new" variant="primary">Make clips now</LinkButton></div>
        </div>
      </section>
    </div>
  );
}
