import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CompanyMark, JobFacts } from "../components/jobs";
import { Badge, Spinner, fmtDate, scoreColor } from "../components/ui";
import { api, type Application } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function Applications() {
  const { t, lang } = useI18n();
  const [rows, setRows] = useState<Application[] | null>(null);
  useEffect(() => {
    api.get<Application[]>("/applications").then(setRows).catch(() => setRows([]));
  }, []);
  if (!rows) return <Spinner />;

  const status = (a: Application): [string, "neutral" | "good" | "warn" | "bad" | "info"] => {
    if (a.status === "in_progress") return [t("as_unfinished"), "warn"];
    if (a.status === "processing") return [t("as_processing"), "info"];
    if (a.status === "failed") return [t("st_failed"), "bad"];
    return { new: [t("as_new"), "neutral"], shortlisted: [t("as_shortlisted"), "good"], rejected: [t("as_rejected"), "bad"], hired: [t("as_hired"), "good"] }[a.review_status] as [string, "neutral"];
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold text-ink">{t("apps_title")}</h1>
        <Link to="/app/board" className="rounded-xl bg-nile px-4 py-2.5 text-sm font-medium text-white dark:text-paper">{t("browse_jobs")}</Link>
      </div>
      {rows.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line p-8 text-center text-muted">{t("apps_empty")}</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((a) => {
            const [label, tone] = status(a);
            return (
              <li key={a.id} className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5 sm:flex-row sm:items-center">
                <CompanyMark name={a.company} />
                <div className="min-w-0 flex-1 space-y-2">
                  <div>
                    <Link to={`/apply/${a.share_token}`} className="text-lg font-semibold text-ink hover:text-nile">{a.title}</Link>
                    <p className="text-[15px] text-muted">{a.company} · {fmtDate(a.created_at, lang)}</p>
                  </div>
                  <JobFacts job={{ ...a, salary: null, deadline: null }} showDeadline={false} />
                </div>
                <div className="flex items-center gap-4 sm:flex-col sm:items-end sm:gap-2">
                  <Badge tone={tone}>{label}</Badge>
                  {a.status === "in_progress" ? (
                    <Link to={`/app/interview/${a.id}`} className="text-sm font-medium text-nile hover:underline">{t("finish_interview")}</Link>
                  ) : a.status === "completed" ? (
                    <Link to={`/app/report/${a.id}`} className="flex items-baseline gap-1.5 text-sm font-medium text-nile hover:underline">
                      <span className="font-display text-xl font-semibold tabular" style={{ color: scoreColor(a.overall_score) }}>{a.overall_score != null ? Math.round(a.overall_score) : "–"}</span>
                      {t("view_report")}
                    </Link>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
