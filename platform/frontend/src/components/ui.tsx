import { Loader2 } from "lucide-react";
import { useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";
import { api, type Catalog } from "../lib/api";
import { useI18n } from "../lib/i18n";

/* ---------- brand ---------- */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2 font-display text-lg font-semibold text-ink">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="var(--color-nile)" />
        <g fill="var(--color-amber)">
          <rect x="6" y="13" width="3" height="6" rx="1.5" />
          <rect x="11" y="9" width="3" height="14" rx="1.5" />
          <rect x="16" y="6" width="3" height="20" rx="1.5" />
          <rect x="21" y="11" width="3" height="10" rx="1.5" />
        </g>
      </svg>
      EvalBot
    </span>
  );
}

/* ---------- waveform: the visual signature (voice) ---------- */
export function Waveform({ levels, bars = 28, animated = false, className = "", color = "var(--color-amber)" }:
  { levels?: number[]; bars?: number; animated?: boolean; className?: string; color?: string }) {
  const values = levels ?? Array.from({ length: bars }, (_, i) => 0.35 + 0.65 * Math.abs(Math.sin(i * 1.7) * Math.cos(i * 0.6)));
  return (
    <div className={`flex h-full items-center gap-[3px] ${className}`} aria-hidden="true">
      {values.map((v, i) => (
        <span
          key={i}
          className={`block w-[4px] rounded-full ${animated ? "wave-bar" : ""}`}
          style={{
            height: `${Math.max(8, Math.min(1, v) * 100)}%`,
            background: color,
            animationDelay: animated ? `${(i % 9) * 0.11}s` : undefined,
            transition: levels ? "height 80ms linear" : undefined,
          }}
        />
      ))}
    </div>
  );
}

/* ---------- buttons & fields ---------- */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "outline" | "danger"; busy?: boolean; size?: "md" | "lg" };
export function Button({ variant = "primary", busy, size = "md", className = "", children, disabled, ...rest }: BtnProps) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const sizes = size === "lg" ? "px-6 py-3.5 text-base" : "px-4 py-2.5 text-[15px]";
  const styles = {
    primary: "bg-nile text-white hover:bg-nile-deep dark:text-paper",
    quiet: "text-ink hover:bg-sunken",
    outline: "border border-line bg-surface text-ink hover:border-nile hover:text-nile",
    danger: "bg-danger text-white hover:opacity-90",
  }[variant];
  return (
    <button className={`${base} ${sizes} ${styles} ${className}`} disabled={disabled || busy} {...rest}>
      {busy && <Loader2 size={16} className="animate-spin" />}
      {children}
    </button>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

const inputCls = "w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-[15px] text-ink placeholder:text-muted/70 focus:border-nile focus:outline-none";
export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={`${inputCls} ${p.className ?? ""}`} />;
export const Textarea = (p: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...p} className={`${inputCls} min-h-28 ${p.className ?? ""}`} />;
export function Select({ value, onChange, options, className = "" }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; className?: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={`${inputCls} ${className}`}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Panel({ children, className = "", title, action }: { children: ReactNode; className?: string; title?: ReactNode; action?: ReactNode }) {
  return (
    <section className={`rounded-2xl border border-line bg-surface p-5 sm:p-6 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-lg font-semibold text-ink">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-muted">
      <Loader2 className="animate-spin" size={20} /> {label}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger" role="alert">{children}</p>;
}

/* ---------- score visuals ---------- */
export function scoreColor(v: number | null | undefined, max = 100) {
  if (v == null) return "var(--color-muted)";
  const r = v / max;
  return r >= 0.7 ? "var(--color-nile)" : r >= 0.5 ? "var(--color-amber)" : "var(--color-danger)";
}

export function ScoreRing({ value, size = 120, max = 100, label }: { value: number | null; size?: number; max?: number; label?: string }) {
  const r = size / 2 - 9;
  const c = 2 * Math.PI * r;
  const v = value == null ? 0 : Math.max(0, Math.min(max, value)) / max;
  return (
    <div className="relative inline-flex flex-none items-center justify-center" style={{ width: size, height: size }} role="img" aria-label={`${label ?? ""} ${value ?? "–"}`}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-sunken)" strokeWidth="9" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={scoreColor(value, max)} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${c * v} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <span className="absolute font-display font-semibold tabular text-ink" style={{ fontSize: size * 0.28 }}>
        {value == null ? "–" : Math.round(value)}
      </span>
    </div>
  );
}

export function Meter({ value, max = 100, color }: { value: number; max?: number; color?: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-sunken">
      <div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.min(100, (value / max) * 100))}%`, background: color ?? scoreColor(value, max) }} />
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" | "info" }) {
  const t = {
    neutral: "bg-sunken text-muted",
    good: "bg-nile-soft text-nile-deep",
    warn: "bg-amber-soft text-ink",
    bad: "bg-danger-soft text-danger",
    info: "bg-nile-soft text-nile",
  }[tone];
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${t}`}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const map: Record<string, [string, "neutral" | "good" | "warn" | "bad" | "info"]> = {
    in_progress: [t("st_in_progress"), "warn"], processing: [t("st_processing"), "info"],
    completed: [t("st_completed"), "good"], failed: [t("st_failed"), "bad"],
  };
  const [label, tone] = map[status] ?? [status, "neutral"];
  return <Badge tone={tone}>{label}</Badge>;
}

/* ---------- data hooks ---------- */
let catalogCache: Catalog | null = null;
export function useCatalog(): Catalog | null {
  const [c, setC] = useState<Catalog | null>(catalogCache);
  useEffect(() => {
    if (!catalogCache) api.get<Catalog>("/catalog").then((x) => { catalogCache = x; setC(x); }).catch(() => undefined);
  }, []);
  return c;
}

export function useTheme(): [boolean, () => void] {
  const [dark, setDark] = useState(() => {
    try {
      const s = localStorage.getItem("evalbot_theme");
      if (s) return s === "dark";
    } catch {
      /* ignore */
    }
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("evalbot_theme", dark ? "dark" : "light");
    } catch {
      /* ignore */
    }
  }, [dark]);
  return [dark, () => setDark((d) => !d)];
}

export function fmtDate(iso: string, lang: string) {
  return new Date(iso).toLocaleDateString(lang === "ar" ? "ar-EG" : "en-GB", { day: "numeric", month: "short", year: "numeric" });
}
