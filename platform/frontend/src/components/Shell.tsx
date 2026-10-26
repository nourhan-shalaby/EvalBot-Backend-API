import { Briefcase, History, LayoutDashboard, LogOut, Menu, Moon, Plus, Settings, Sun, UploadCloud, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { Logo, useTheme } from "./ui";

export function LangSwitch() {
  const { lang, setLang } = useI18n();
  return (
    <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} className="rounded-lg px-2.5 py-1.5 text-sm font-medium text-muted hover:bg-sunken hover:text-ink"
      aria-label="Change language">
      {lang === "ar" ? "English" : "العربية"}
    </button>
  );
}

export function ThemeSwitch() {
  const [dark, toggle] = useTheme();
  const { t } = useI18n();
  return (
    <button onClick={toggle} className="rounded-lg p-2 text-muted hover:bg-sunken hover:text-ink" aria-label={dark ? t("theme_light") : t("theme_dark")}>
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}

export function PublicHeader() {
  const { profile } = useAuth();
  const { t } = useI18n();
  return (
    <header className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-5 sm:px-6">
      <Link to="/" aria-label="EvalBot home"><Logo /></Link>
      <nav className="flex items-center gap-1 sm:gap-2">
        <LangSwitch />
        <ThemeSwitch />
        {profile ? (
          <Link to="/app" className="rounded-xl bg-nile px-4 py-2 text-sm font-medium text-white dark:text-paper">{t("nav_dashboard")}</Link>
        ) : (
          <>
            <Link to="/login" className="hidden rounded-xl px-3 py-2 text-sm font-medium text-ink hover:bg-sunken sm:inline-block">{t("sign_in")}</Link>
            <Link to="/signup" className="rounded-xl bg-nile px-4 py-2 text-sm font-medium text-white dark:text-paper">{t("get_started")}</Link>
          </>
        )}
      </nav>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { profile, signOut } = useAuth();
  const { t } = useI18n();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const isRecruiter = profile?.role === "recruiter";
  const links = isRecruiter
    ? [
        { to: "/app/jobs", icon: Briefcase, label: t("nav_jobs") },
        { to: "/app", icon: LayoutDashboard, label: t("nav_dashboard"), end: true },
        { to: "/app/new", icon: Plus, label: t("nav_new") },
        { to: "/app/history", icon: History, label: t("nav_history") },
      ]
    : [
        { to: "/app", icon: LayoutDashboard, label: t("nav_dashboard"), end: true },
        { to: "/app/new", icon: Plus, label: t("nav_new") },
        { to: "/app/history", icon: History, label: t("nav_history") },
      ];
  const item = "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors";
  const sidebar = (
    <div className="flex h-full flex-col gap-1 p-4">
      <Link to="/" className="mb-6 px-2" onClick={() => setOpen(false)}><Logo /></Link>
      {links.map((l) => (
        <NavLink key={l.to} to={l.to} end={l.end} onClick={() => setOpen(false)}
          className={({ isActive }) => `${item} ${isActive ? "bg-nile-soft text-nile-deep" : "text-muted hover:bg-sunken hover:text-ink"}`}>
          <l.icon size={18} /> {l.label}
        </NavLink>
      ))}
      <a href="/demo" className={`${item} text-muted hover:bg-sunken hover:text-ink`}><UploadCloud size={18} /> {t("nav_quick")}</a>
      <div className="mt-auto flex flex-col gap-1 border-t border-line pt-3">
        <NavLink to="/app/settings" onClick={() => setOpen(false)}
          className={({ isActive }) => `${item} ${isActive ? "bg-nile-soft text-nile-deep" : "text-muted hover:bg-sunken hover:text-ink"}`}>
          <Settings size={18} /> {t("nav_settings")}
        </NavLink>
        <button className={`${item} text-muted hover:bg-sunken hover:text-ink`} onClick={async () => { await signOut(); nav("/"); }}>
          <LogOut size={18} className="rtl:rotate-180" /> {t("sign_out")}
        </button>
        <div className="flex items-center gap-1 px-1 pt-2"><LangSwitch /><ThemeSwitch /></div>
        {profile && <p className="truncate px-3 pt-1 text-xs text-muted">{profile.full_name || profile.email}{profile.company ? `, ${profile.company.name}` : ""}</p>}
      </div>
    </div>
  );
  return (
    <div className="min-h-screen lg:flex">
      <aside className="sticky top-0 hidden h-screen w-64 flex-none border-e border-line bg-surface lg:block">{sidebar}</aside>
      <div className="flex items-center justify-between border-b border-line bg-surface px-4 py-3 lg:hidden">
        <Link to="/app"><Logo size={24} /></Link>
        <button onClick={() => setOpen(true)} className="rounded-lg p-2 text-ink hover:bg-sunken" aria-label="Menu"><Menu size={22} /></button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 start-0 w-72 bg-surface shadow-xl">
            <button onClick={() => setOpen(false)} className="absolute end-3 top-4 rounded-lg p-2 text-muted hover:bg-sunken" aria-label="Close"><X size={20} /></button>
            {sidebar}
          </div>
        </div>
      )}
      <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
