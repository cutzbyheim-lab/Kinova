import { useQuery } from "@tanstack/react-query";
import {
  BarChart3, CalendarDays, Clapperboard, Flag, FolderOpen, LayoutGrid, Menu, MessageSquare, Settings, Sparkles, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../lib/api";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/studio", label: "Studio", icon: Clapperboard },
  { to: "/campaigns", label: "Campaigns", icon: Flag },
  { to: "/library", label: "Content Library", icon: FolderOpen },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/brands", label: "Brand Brain", icon: Sparkles },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/assistant", label: "AI Assistant", icon: MessageSquare },
  { to: "/settings", label: "Settings", icon: Settings },
];

function Wordmark() {
  return <span className="text-[30px] font-extrabold tracking-[-0.04em]">kinova<span className="text-orange">.</span></span>;
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const status = useQuery({ queryKey: ["status"], queryFn: api.status, refetchInterval: 30_000 });
  useEffect(() => setOpen(false), [loc.pathname]);

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-cream focus:px-4 focus:py-2 focus:text-ink">
        Skip to content
      </a>
      {/* Mobile top bar */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-ink/95 px-4 py-3 backdrop-blur lg:hidden">
        <Wordmark />
        <button type="button" onClick={() => setOpen((o) => !o)} aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-line-3">
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      <nav aria-label="Main"
        className={`${open ? "flex" : "hidden"} z-20 flex-col gap-7 border-line bg-ink-2 px-4 py-6 lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-[244px] lg:shrink-0 lg:border-r`}>
        <div className="hidden px-2.5 lg:block"><Wordmark /></div>
        <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink to={to} end={end}
                className={({ isActive }) =>
                  `group flex min-h-11 items-center gap-3 rounded-full px-3.5 text-[15px] no-underline transition-colors duration-150 ${
                    isActive ? "bg-cream font-bold text-ink" : "font-medium text-mute hover:bg-panel-3 hover:text-cream"}`}>
                <Icon size={18} strokeWidth={1.8} aria-hidden className="transition-transform duration-200 group-hover:scale-110" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="mt-auto flex flex-col gap-1 rounded-2xl bg-panel-3 px-4 py-3.5">
          <span className="text-[13px] font-bold">{status.data?.organization.name ?? "Local studio"}</span>
          <span className="text-[13px] text-dim">Local mode · single user</span>
          <span className="mt-1 flex items-center gap-2 text-[12px] text-dim">
            <span className={`h-2 w-2 rounded-full ${status.data?.worker.online ? "bg-ok" : "bg-[#6e625b]"}`} aria-hidden />
            {status.isLoading ? "Checking worker…" : status.data?.worker.online ? "Worker ready" : "Worker offline"}
          </span>
        </div>
      </nav>

      <main id="main" className="min-w-0 flex-1 px-5 pb-16 pt-7 sm:px-8 lg:px-11">
        <Outlet />
      </main>
    </div>
  );
}
