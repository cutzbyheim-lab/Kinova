import { AlertTriangle, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";

type Variant = "primary" | "cream" | "ghost" | "danger";

const variants: Record<Variant, string> = {
  primary: "bg-orange text-ink hover:bg-[#ff7f47] active:bg-orange-deep",
  cream: "bg-cream text-ink hover:bg-white",
  ghost: "bg-transparent text-cream border border-line-3 hover:border-cream hover:bg-panel-2",
  danger: "bg-transparent text-danger border border-line-3 hover:border-danger",
};

export function Button({
  variant = "ghost", busy, icon, children, className = "", ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean; icon?: ReactNode }) {
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || busy}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-[15px] font-semibold
        transition-[background,border-color,transform] duration-150 active:scale-[0.98]
        disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
    >
      {busy ? <Loader2 size={17} className="animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

export function LinkButton({ to, variant = "ghost", icon, children, className = "" }:
  { to: string; variant?: Variant; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Link
      to={to}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-[15px] font-semibold
        no-underline transition-colors duration-150 ${variants[variant]} ${className}`}
    >
      {icon}
      {children}
    </Link>
  );
}

export function SectionHead({ num, title, action }: { num?: string; title: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-3">
      <div className="flex items-baseline gap-3">
        {num && <span className="serif-i text-[40px] leading-none text-violet">{num}</span>}
        <h2 className="m-0 text-[22px] font-bold tracking-tight">{title}</h2>
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, accent, children }:
  { eyebrow: string; title: string; accent?: string; children?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-6 animate-rise">
      <div className="flex flex-col gap-3">
        <span className="eyebrow">{eyebrow}</span>
        <h1 className="m-0 text-[clamp(44px,6vw,76px)] font-extrabold leading-[0.92] tracking-[-0.045em]">
          {title}{accent && <> <span className="serif-i tracking-[-0.02em] text-orange">{accent}</span></>}
        </h1>
      </div>
      {children && <div className="flex flex-wrap gap-3">{children}</div>}
    </header>
  );
}

const statusStyle: Record<string, string> = {
  queued: "border-line-3 text-mute",
  running: "border-orange text-orange",
  succeeded: "border-ok/60 text-ok",
  partial: "border-warn/60 text-warn",
  failed: "border-danger/60 text-danger",
  ready: "border-ok/60 text-ok",
  rendering: "border-orange text-orange",
};
const statusText: Record<string, string> = {
  queued: "Queued", running: "Producing", succeeded: "Done", partial: "Partly done",
  failed: "Failed", ready: "Ready", rendering: "Rendering",
};

export function StatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold ${statusStyle[status] ?? "border-line-3 text-mute"}`}>
      {status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-orange" aria-hidden />}
      {statusText[status] ?? status}
    </span>
  );
}

export function Dot({ on, label }: { on: boolean; label: string }) {
  return (
    <span className="inline-flex h-9 items-center gap-2 rounded-full border border-line-2 px-3.5 text-[13px] text-mute">
      <span className={`h-2 w-2 rounded-full ${on ? "bg-ok" : "bg-[#6e625b]"}`} aria-hidden />
      {label}
    </span>
  );
}

export function EmptyState({ title, body, children, art = true }:
  { title: string; body: string; children?: ReactNode; art?: boolean }) {
  return (
    <div className="relative overflow-hidden rounded-[var(--radius-card)] border border-dashed border-line-3 bg-ink-2 p-8 sm:p-10">
      {art && (
        <div aria-hidden className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full opacity-60 blur-2xl"
          style={{ background: "radial-gradient(circle, rgba(255,106,43,.35), transparent 65%)" }} />
      )}
      <div className="relative flex max-w-xl flex-col gap-3">
        <p className="m-0 text-[26px] font-semibold leading-tight">{title}</p>
        <p className="m-0 text-[15px] leading-relaxed text-mute">{body}</p>
        {children && <div className="mt-2 flex flex-wrap gap-3">{children}</div>}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="flex flex-wrap items-center gap-4 rounded-2xl border border-danger/40 bg-[#2a1714] p-5">
      <AlertTriangle className="text-danger" size={22} aria-hidden />
      <p className="m-0 flex-1 text-[15px] text-cream">{msg}</p>
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-2xl ${className}`} aria-hidden />;
}

export function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[13px] font-semibold uppercase tracking-[0.1em] text-dim">{label}</span>
      <span className="serif-i text-[44px] leading-none text-cream">{value}</span>
      {hint && <span className="text-[13px] text-faint">{hint}</span>}
    </div>
  );
}

export const gradientFor = (seed: string) => {
  const palettes = [
    ["#5A2A16", "#15110F"], ["#33285A", "#15110F"], ["#3A302B", "#15110F"], ["#4A2131", "#15110F"],
  ];
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const [a, b] = palettes[h % palettes.length]!;
  return `linear-gradient(165deg, ${a}, ${b})`;
};
