import { Play } from "lucide-react";
import { Link } from "react-router-dom";
import type { Output } from "../lib/types";
import { fmtDuration } from "../lib/format";
import { gradientFor } from "./ui";

export default function ClipTile({ o, to }: { o: Output; to?: string }) {
  const body = (
    <>
      <div className="relative aspect-[9/16] overflow-hidden rounded-xl border border-line"
        style={{ background: gradientFor(o.id) }}>
        {o.thumbnail_url && (
          <img src={o.thumbnail_url} alt="" loading="lazy"
            className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
        )}
        <span className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-orange text-ink"><Play size={20} fill="currentColor" aria-hidden /></span>
        </span>
        <span className="absolute bottom-2 left-2 rounded-md bg-ink/85 px-1.5 py-0.5 font-mono text-[11px]">{fmtDuration(o.duration_s)}</span>
        {o.approved && <span className="absolute right-2 top-2 rounded-full bg-ok px-2 py-0.5 text-[11px] font-bold text-ink">Approved</span>}
      </div>
      <span className="mt-2 block truncate text-[14px] font-bold">{o.title || `${o.style} cut`}</span>
      <span className="serif-i block text-[15px] capitalize text-dim">{o.style}</span>
    </>
  );
  return to ? <Link to={to} className="group block min-w-0 no-underline">{body}</Link> : <div className="group min-w-0">{body}</div>;
}
