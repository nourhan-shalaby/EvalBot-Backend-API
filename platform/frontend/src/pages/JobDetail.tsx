import { Download, Pencil, Search, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Distribution, Funnel, KpiGrid, Signals, SkillsPanel, TraitsPanel, reviewTone, signalTone } from "../components/hiring";
import { JobFacts, Skills } from "../components/jobs";
import { Badge, Button, Input, Panel, Select, Spinner, StatusBadge, fmtDate, scoreColor, useCatalog } from "../components/ui";
import { api, type CandidateRow, type HiringStats, type Job } from "../lib/api";
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
  const [stats, setStats] = useState<HiringStats | null>(null);
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState("0");
  const [exporting, setExporting] = useState(false);
  useEffect(() => {
    api.get<Job>(`/jobs/${id}`).then(setJob);
    api.get<CandidateRow[]>(`/jobs/${id}/candidates`).then(setRows);
  }, [id]);
  useEffect(() => {
    api.get<HiringStats>(`/jobs/${id}/stats?lang=${lang}`).then(setStats).catch(() => undefined);
  }, [id, lang]);
  if (!job || !rows) return <Spinner />;
  const needle = search.trim().toLowerCase();
  const shown = rows.filter((r) => (filter === "all" || r.review_status === filter)
    && (!needle || `${r.full_name} ${r.email}`.toLowerCase().includes(needle))
    && (+minScore === 0 || (r.overall_score ?? -1) >= +minScore));
  const sigTone = signalTone;
  const rvTone = reviewTone;
  const exportCsv = async () => {
    setExporting(true);
    try {
      const blob = await api.blob(`/jobs/${id}/candidates.csv`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `evalbot-${job.title.replace(/[^\w]+/g, "-")}-candidates.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } finally {
      setExporting(false);
    }
  };

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
      <div className="space-y-3">
        <JobFacts job={job} />
        <Skills skills={job.skills} />
        <p className="text-sm text-muted">{job.visibility === "public" ? t("vis_public") : t("vis_link")}. {t("share_hint")}</p>
      </div>

      {stats && stats.totals.applicants > 0 && (
        <>
          <h2 className="pt-2 text-xl font-semibold text-ink">{t("job_stats")}</h2>
          <KpiGrid s={stats.totals} />
          <div className="grid gap-6 lg:grid-cols-3">
            <Funnel data={stats.funnel} />
            <Distribution data={stats.distribution} />
            <Signals data={stats.signals} />
          </div>
        </>
      )}

      <Panel title={t("candidates_title")} action={
        <Button variant="outline" onClick={exportCsv} busy={exporting} disabled={!rows.length}><Download size={16} /> {t("export_csv")}</Button>
      }>
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
          <label className="relative block md:w-64">
            <Search size={16} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("search_candidates")} className="ps-9" aria-label={t("search_candidates")} />
          </label>
          <Select className="md:w-44" value={minScore} onChange={setMinScore}
            options={[0, 50, 60, 70, 80].map((v) => ({ value: String(v), label: v ? `${t("min_score")}: ${v}+` : `${t("min_score")}: –` }))} />
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setFilter(f)} aria-pressed={filter === f}
              className={`rounded-lg px-2.5 py-1 text-sm ${filter === f ? "bg-nile-soft font-medium text-nile-deep" : "text-muted hover:bg-sunken"}`}>
              {f === "all" ? t("all") : t(`rv_${f}`)}
            </button>
          ))}
        </div>
        </div>
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
      {stats && stats.totals.completed > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <TraitsPanel data={stats.traits} />
          <SkillsPanel data={stats.skills} />
        </div>
      )}
      <p className="text-sm text-muted">{t("fairness")}</p>
    </div>
  );
}
