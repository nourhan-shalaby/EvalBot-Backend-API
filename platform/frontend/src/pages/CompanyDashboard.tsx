import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { Distribution, Funnel, KpiGrid, Signals, SkillsPanel, Timeline, TopCandidates, TraitsPanel } from "../components/hiring";
import { Badge, Panel, Spinner, Waveform, fmtDate, scoreColor } from "../components/ui";
import { api, type HiringStats } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function CompanyDashboard() {
  const { t, lang } = useI18n();
  const { profile } = useAuth();
  const [s, setS] = useState<HiringStats | null>(null);
  useEffect(() => {
    if (profile?.company_id) api.get<HiringStats>(`/company/stats?lang=${lang}`).then(setS).catch(() => undefined);
  }, [profile, lang]);
  if (profile && !profile.company_id) return <Navigate to="/app/welcome?as=company" replace />;
  if (!s) return <Spinner />;
  const company = profile?.company?.name || "";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-3xl bg-ink p-6 text-paper sm:flex-row sm:items-center sm:justify-between sm:p-8 dark:bg-sunken dark:text-ink">
        <div>
          <h1 className="text-3xl font-semibold">{t("co_hello", { company })}</h1>
          <p className="mt-1 opacity-80">{t("co_sub")}</p>
          <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm opacity-90">
            <span><b className="tabular">{s.totals.open_jobs}</b> {t("k_open_jobs")}</span>
            <span><b className="tabular">{s.totals.people}</b> {t("k_applicants")}</span>
            {s.totals.avg_minutes != null && <span>{t("k_minutes")}: <b className="tabular">{Math.round(s.totals.avg_minutes)}</b> {t("min")}</span>}
          </p>
        </div>
        <div className="flex items-center gap-5">
          <div className="hidden h-12 w-36 md:block"><Waveform bars={22} color="var(--color-amber)" /></div>
          <Link to="/app/jobs/new" className="inline-flex items-center gap-2 rounded-xl bg-amber px-5 py-3 font-medium text-ink hover:opacity-90"><Plus size={18} /> {t("co_new_job_cta")}</Link>
        </div>
      </div>

      {s.totals.jobs === 0 ? (
        <Panel><p className="text-muted">{t("empty_company")}</p></Panel>
      ) : (
        <>
          <KpiGrid s={s.totals} />
          <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
            <Timeline data={s.timeline} />
            <Funnel data={s.funnel} />
          </div>
          <TopCandidates rows={s.top} />
          <div className="grid gap-6 lg:grid-cols-2">
            <Distribution data={s.distribution} />
            <Signals data={s.signals} />
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <TraitsPanel data={s.traits} />
            <SkillsPanel data={s.skills} />
          </div>
          <Panel title={t("jobs_table")} action={<Link to="/app/jobs" className="text-sm font-medium text-nile hover:underline">{t("nav_jobs")}</Link>}>
            <div className="-mx-5 overflow-x-auto sm:-mx-6">
              <table className="w-full min-w-[640px] text-[15px]">
                <thead>
                  <tr className="border-b border-line text-sm text-muted">
                    <th className="px-5 py-2 text-start font-medium sm:px-6">{t("c_job")}</th>
                    <th className="py-2 text-start font-medium">{t("k_views")}</th>
                    <th className="py-2 text-start font-medium">{t("k_applicants")}</th>
                    <th className="py-2 text-start font-medium">{t("completed_n")}</th>
                    <th className="py-2 text-start font-medium">{t("k_avg")}</th>
                    <th className="px-5 py-2 text-start font-medium sm:px-6">{t("k_shortlisted")}</th>
                  </tr>
                </thead>
                <tbody>
                  {s.jobs.map((j) => (
                    <tr key={j.id} className="border-b border-line last:border-0">
                      <td className="px-5 py-3 sm:px-6">
                        <Link to={`/app/jobs/${j.id}`} className="font-medium text-ink hover:text-nile">{j.title}</Link>
                        <p className="mt-0.5 flex items-center gap-2 text-xs text-muted">
                          <Badge tone={j.accepting ? "good" : j.status === "draft" ? "neutral" : "bad"}>{t(`jst_${j.accepting ? "open" : j.status === "draft" ? "draft" : "closed"}`)}</Badge>
                          {fmtDate(j.created_at, lang)}
                        </p>
                      </td>
                      <td className="py-3 tabular text-muted">{j.views}</td>
                      <td className="py-3 tabular text-ink">{j.applicants}</td>
                      <td className="py-3 tabular text-ink">{j.completed}</td>
                      <td className="py-3"><span className="font-semibold tabular" style={{ color: scoreColor(j.avg_score) }}>{j.avg_score != null ? Math.round(j.avg_score) : "–"}</span></td>
                      <td className="px-5 py-3 tabular text-ink sm:px-6">{j.shortlisted}{j.hired ? ` (${j.hired} ${t("k_hired")})` : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <p className="text-sm text-muted">{t("fairness")}</p>
        </>
      )}
    </div>
  );
}
