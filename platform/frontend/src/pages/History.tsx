import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Spinner, StatusBadge, fmtDate, scoreColor, useCatalog } from "../components/ui";
import { api, type SessionRow } from "../lib/api";
import { trackName, useI18n } from "../lib/i18n";

export function SessionList({ rows, onDelete }: { rows: SessionRow[]; onDelete?: (id: string) => void }) {
  const { t, lang } = useI18n();
  const catalog = useCatalog();
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
      {rows.map((s) => {
        const href = s.status === "in_progress" ? `/app/interview/${s.id}` : `/app/report/${s.id}`;
        return (
          <li key={s.id} className="flex items-center gap-4 px-4 py-3.5 hover:bg-sunken/60 sm:px-5">
            <div className="flex h-12 w-12 flex-none items-center justify-center rounded-xl bg-sunken font-display text-lg font-semibold tabular"
              style={{ color: scoreColor(s.overall_score) }}>
              {s.overall_score != null ? Math.round(s.overall_score) : "–"}
            </div>
            <Link to={href} className="min-w-0 flex-1">
              <p className="truncate font-medium text-ink">{s.job_title || s.role || trackName(catalog?.tracks, s.track, lang)}</p>
              <p className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-muted">
                <span>{fmtDate(s.created_at, lang)}</span>
                <Badge>{s.mode === "job" ? t("job") : t("mock")}</Badge>
                <StatusBadge status={s.status} />
                {s.status === "in_progress" && <span>{t("answered_n", { a: s.answered, b: s.planned })}</span>}
              </p>
            </Link>
            <Link to={href} className="hidden rounded-lg px-3 py-1.5 text-sm font-medium text-nile hover:bg-nile-soft sm:inline-block">
              {s.status === "in_progress" ? t("resume") : t("view_report")}
            </Link>
            {onDelete && s.mode !== "job" && (
              <button onClick={() => onDelete(s.id)} className="rounded-lg p-2 text-muted hover:bg-danger-soft hover:text-danger" aria-label={t("delete")}>
                <Trash2 size={16} />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function History() {
  const { t } = useI18n();
  const [rows, setRows] = useState<SessionRow[] | null>(null);
  const load = () => api.get<SessionRow[]>("/sessions").then(setRows);
  useEffect(() => {
    load();
  }, []);
  const del = async (id: string) => {
    if (!confirm(t("delete_confirm"))) return;
    await api.del(`/sessions/${id}`);
    load();
  };
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold text-ink">{t("nav_history")}</h1>
        <Link to="/app/new" className="rounded-xl bg-nile px-4 py-2.5 text-sm font-medium text-white dark:text-paper">{t("nav_new")}</Link>
      </div>
      {!rows ? <Spinner /> : rows.length === 0 ? <p className="text-muted">{t("empty_dash")}</p> : <SessionList rows={rows} onDelete={del} />}
    </div>
  );
}
