import { Pencil, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Panel, Spinner, StatusBadge, fmtDate, scoreColor, useCatalog } from "../components/ui";
import { api, type CandidateRow, type Job } from "../lib/api";
import { trackName, useI18n } from "../lib/i18n";
import { CopyLink } from "./Jobs";

const FILTERS = ["all", "new", "shortlisted", "rejected", "hired"] as const;

export default function JobDetail() {
  const { id } = useParams();
  const { t, lang } = useI18n();
  const catalog = useCatalog();
  const nav = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [rows, setRows] = useState<CandidateRow[] | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  useEffect(() => {
    api.get<Job>(`/jobs/${id}`).then(setJob);
    api.get<CandidateRow[]>(`/jobs/${id}/candidates`).then(setRows);
  }, [id]);
  if (!job || !rows) return <Spinner />;
  const shown = rows.filter((r) => filter === "all" || r.review_status === filter);
  const sigTone = (s: string | null) => (s === "strong_yes" || s === "yes" ? "good" : s === "maybe" ? "warn" : s === "no" ? "bad" : "neutral");
  const rvTone = { new: "neutral", shortlisted: "info", rejected: "bad", hired: "good" } as const;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-ink">{job.title}</h1>
          <p className="mt-1 text-muted">{trackName(catalog?.tracks, job.track, lang)}, {t(`lv_${job.level}` as "lv_junior")}, {job.questions.length} {t("questions")}</p>
        </div>
        <div className="flex items-center gap-2">
          <CopyLink token={job.share_token} />
          <Link to={`/app/jobs/${job.id}/edit`} className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-ink hover:border-nile"><Pencil size={14} /> {t("edit")}</Link>
        </div>
      </div>
      <p className="text-sm text-muted">{t("share_hint")}</p>

      <Panel title={t("candidates_title")} action={
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setFilter(f)} aria-pressed={filter === f}
              className={`rounded-lg px-2.5 py-1 text-sm ${filter === f ? "bg-nile-soft font-medium text-nile-deep" : "text-muted hover:bg-sunken"}`}>
              {f === "all" ? t("all") : t(`rv_${f}`)}
            </button>
          ))}
        </div>
      }>
        {shown.length === 0 ? (
          <p className="py-6 text-center text-muted">{t("empty_candidates")}</p>
        ) : (
          <div className="-mx-5 overflow-x-auto sm:-mx-6">
            <table className="w-full min-w-[640px] text-start text-[15px]">
              <thead>
                <tr className="border-b border-line text-sm text-muted">
                  <th className="px-5 py-2 text-start font-medium sm:px-6">#</th>
                  <th className="py-2 text-start font-medium">{t("c_name")}</th>
                  <th className="py-2 text-start font-medium">{t("c_score")}</th>
                  <th className="py-2 text-start font-medium">{t("c_signal")}</th>
                  <th className="py-2 text-start font-medium">{t("c_status")}</th>
                  <th className="px-5 py-2 text-start font-medium sm:px-6">{t("c_date")}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r, i) => (
                  <tr key={r.id} onClick={() => nav(`/app/report/${r.id}`)} className="cursor-pointer border-b border-line last:border-0 hover:bg-sunken/60">
                    <td className="px-5 py-3 tabular text-muted sm:px-6">{i + 1}</td>
                    <td className="py-3">
                      <p className="font-medium text-ink">{r.full_name || r.email}</p>
                      {r.rating && <p className="flex">{Array.from({ length: r.rating }).map((_, k) => <Star key={k} size={12} className="fill-amber text-amber" />)}</p>}
                    </td>
                    <td className="py-3">
                      {r.status === "completed" ? (
                        <span className="font-display text-lg font-semibold tabular" style={{ color: scoreColor(r.overall_score) }}>{r.overall_score != null ? Math.round(r.overall_score) : "–"}</span>
                      ) : <StatusBadge status={r.status} />}
                    </td>
                    <td className="py-3">{r.hiring_signal && <Badge tone={sigTone(r.hiring_signal)}>{t(`sig_${r.hiring_signal}` as "sig_yes")}</Badge>}</td>
                    <td className="py-3"><Badge tone={rvTone[r.review_status]}>{t(`rv_${r.review_status}`)}</Badge></td>
                    <td className="px-5 py-3 text-sm text-muted sm:px-6">{fmtDate(r.created_at, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <p className="text-sm text-muted">{t("fairness")}</p>
    </div>
  );
}
