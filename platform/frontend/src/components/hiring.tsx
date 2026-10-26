import { Star } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HiringStats } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Badge, Meter, Panel, scoreColor } from "./ui";

const tip = { background: "var(--color-surface)", border: "1px solid var(--color-line)", borderRadius: 12, color: "var(--color-ink)" };

export const signalTone = (s: string | null) => (s === "strong_yes" || s === "yes" ? "good" : s === "maybe" ? "warn" : s === "no" ? "bad" : "neutral");
export const reviewTone = { new: "neutral", shortlisted: "info", rejected: "bad", hired: "good" } as const;

export function Kpi({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: boolean }) {
  return (
    <div className={`rounded-2xl border p-4 ${accent ? "border-amber bg-amber-soft" : "border-line bg-surface"}`}>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-display text-3xl font-semibold tabular text-ink">{value ?? "–"}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </div>
  );
}

export function KpiGrid({ s }: { s: HiringStats["totals"] }) {
  const { t } = useI18n();
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Kpi label={t("k_applicants")} value={s.applicants} sub={s.views ? `${t("k_views")}: ${s.views}` : undefined} />
      <Kpi label={t("k_completed")} value={s.completed} sub={s.completion_rate != null ? `${t("k_completion")}: ${s.completion_rate}%` : undefined} />
      <Kpi label={t("k_avg")} value={s.avg_score != null ? Math.round(s.avg_score) : "–"}
        sub={s.median_score != null ? `${t("k_median")}: ${Math.round(s.median_score)} · ${t("k_best")}: ${Math.round(s.best_score ?? 0)}` : t("out_of_100")} />
      <Kpi label={t("k_to_review")} value={s.to_review} accent={s.to_review > 0}
        sub={`${t("k_shortlisted")}: ${s.shortlisted} · ${t("k_hired")}: ${s.hired}`} />
    </div>
  );
}

export function Funnel({ data }: { data: HiringStats["funnel"] }) {
  const { t } = useI18n();
  const shown = data.filter((d) => d.stage !== "views" || d.count > 0);
  const max = Math.max(1, ...shown.map((d) => d.count));
  return (
    <Panel title={t("funnel_title")}>
      <ol className="space-y-3">
        {shown.map((d, i) => {
          const prev = i > 0 ? shown[i - 1].count : null;
          const conv = prev && d.count <= prev ? Math.round((100 * d.count) / prev) : null;
          return (
            <li key={d.stage}>
              <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
                <span className="text-ink">{t(`fn_${d.stage}` as "fn_views")}</span>
                <span className="tabular text-muted"><span className="font-semibold text-ink">{d.count}</span>{conv != null && ` · ${conv}%`}</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-sunken">
                <div className="h-full rounded-full bg-nile" style={{ width: `${Math.max(2, (100 * d.count) / max)}%`, opacity: 1 - i * 0.13 }} />
              </div>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}

export function Timeline({ data }: { data: HiringStats["timeline"] }) {
  const { t, lang } = useI18n();
  const fmt = (d: string) => new Date(d).toLocaleDateString(lang === "ar" ? "ar-EG" : "en-GB", { day: "numeric", month: "short" });
  return (
    <Panel title={t("timeline_title")}>
      <div className="h-56" dir="ltr">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ left: -24, right: 8, top: 8 }}>
            <CartesianGrid stroke="var(--color-line)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={fmt} stroke="var(--color-muted)" fontSize={12} interval={6} />
            <YAxis allowDecimals={false} stroke="var(--color-muted)" fontSize={12} />
            <Tooltip contentStyle={tip} labelFormatter={(l) => fmt(String(l))} />
            <Area type="monotone" dataKey="applicants" name={t("k_applicants")} stroke="var(--color-nile)" fill="var(--color-nile)" fillOpacity={0.15} strokeWidth={2} />
            <Area type="monotone" dataKey="completed" name={t("k_completed")} stroke="var(--color-amber)" fill="var(--color-amber)" fillOpacity={0.12} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

export function Distribution({ data }: { data: HiringStats["distribution"] }) {
  const { t } = useI18n();
  return (
    <Panel title={t("dist_title")}>
      <div className="h-56" dir="ltr">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: -24, right: 8, top: 8 }}>
            <CartesianGrid stroke="var(--color-line)" vertical={false} />
            <XAxis dataKey="range" stroke="var(--color-muted)" fontSize={11} />
            <YAxis allowDecimals={false} stroke="var(--color-muted)" fontSize={12} />
            <Tooltip contentStyle={tip} cursor={{ fill: "var(--color-sunken)" }} />
            <Bar dataKey="count" name={t("k_applicants")} radius={[6, 6, 0, 0]}>
              {data.map((d, i) => <Cell key={d.range} fill={scoreColor(i * 10 + 5)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

export function Signals({ data }: { data: HiringStats["signals"] }) {
  const { t } = useI18n();
  const order = ["strong_yes", "yes", "maybe", "no"] as const;
  const colors = { strong_yes: "var(--color-nile-deep)", yes: "var(--color-nile)", maybe: "var(--color-amber)", no: "var(--color-danger)" };
  const total = order.reduce((a, k) => a + data[k], 0);
  return (
    <Panel title={t("signals_title")}>
      {total === 0 ? <p className="text-sm text-muted">–</p> : (
        <>
          <div className="flex h-4 overflow-hidden rounded-full bg-sunken" role="img" aria-label={t("signals_title")}>
            {order.map((k) => data[k] > 0 && <div key={k} style={{ width: `${(100 * data[k]) / total}%`, background: colors[k] }} />)}
          </div>
          <ul className="mt-4 space-y-2">
            {order.map((k) => (
              <li key={k} className="flex items-center gap-2 text-sm">
                <span className="h-3 w-3 flex-none rounded-sm" style={{ background: colors[k] }} />
                <span className="text-ink">{t(`sig_${k}`)}</span>
                <span className="ms-auto tabular text-muted">{data[k]} · {Math.round((100 * data[k]) / total)}%</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}

export function TraitsPanel({ data }: { data: HiringStats["traits"] }) {
  const { t } = useI18n();
  if (!data.length) return null;
  return (
    <Panel title={t("traits_title")}>
      <p className="-mt-2 mb-4 text-sm text-muted">{t("traits_sub")}</p>
      <ul className="space-y-3">
        {data.map((x) => (
          <li key={x.trait}>
            <div className="mb-1 flex justify-between gap-2 text-sm"><span className="text-ink">{x.label}</span><span className="tabular text-muted">{x.avg_percentile}%</span></div>
            <Meter value={x.avg_percentile} color="var(--color-nile)" />
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function SkillsPanel({ data }: { data: HiringStats["skills"] }) {
  const { t } = useI18n();
  if (!data.length) return null;
  return (
    <Panel title={t("skills_pool")}>
      <ul className="space-y-3">
        {data.map((s) => (
          <li key={s.skill}>
            <div className="mb-1 flex justify-between gap-2 text-sm"><span className="ltr truncate text-ink">{s.skill}</span><span className="tabular text-muted">{s.avg}/10 · {s.n}</span></div>
            <Meter value={s.avg} max={10} />
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function TopCandidates({ rows, showJob = true }: { rows: HiringStats["top"]; showJob?: boolean }) {
  const { t } = useI18n();
  const nav = useNavigate();
  return (
    <Panel title={t("top_title")}>
      {rows.length === 0 ? <p className="py-4 text-center text-muted">{t("empty_candidates")}</p> : (
        <div className="-mx-5 overflow-x-auto sm:-mx-6">
          <table className="w-full min-w-[600px] text-[15px]">
            <thead>
              <tr className="border-b border-line text-sm text-muted">
                <th className="px-5 py-2 text-start font-medium sm:px-6">#</th>
                <th className="py-2 text-start font-medium">{t("c_name")}</th>
                {showJob && <th className="py-2 text-start font-medium">{t("c_job")}</th>}
                <th className="py-2 text-start font-medium">{t("c_score")}</th>
                <th className="py-2 text-start font-medium">{t("c_signal")}</th>
                <th className="px-5 py-2 text-start font-medium sm:px-6">{t("c_status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id} onClick={() => nav(`/app/report/${r.id}`)} className="cursor-pointer border-b border-line last:border-0 hover:bg-sunken/60">
                  <td className="px-5 py-3 sm:px-6">
                    <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold tabular ${i < 3 ? "bg-amber-soft text-ink" : "text-muted"}`}>{i + 1}</span>
                  </td>
                  <td className="py-3">
                    <p className="font-medium text-ink">{r.full_name || r.email}</p>
                    <p className="flex items-center gap-2 text-xs text-muted">
                      {r.candidate_headline}
                      {r.rating && <span className="flex">{Array.from({ length: r.rating }).map((_, k) => <Star key={k} size={11} className="fill-amber text-amber" />)}</span>}
                    </p>
                  </td>
                  {showJob && <td className="py-3"><Link to={`/app/jobs/${r.job_id}`} onClick={(e) => e.stopPropagation()} className="text-sm text-ink hover:text-nile">{r.job_title}</Link></td>}
                  <td className="py-3"><span className="font-display text-lg font-semibold tabular" style={{ color: scoreColor(r.overall_score) }}>{r.overall_score != null ? Math.round(r.overall_score) : "–"}</span></td>
                  <td className="py-3">{r.hiring_signal && <Badge tone={signalTone(r.hiring_signal)}>{t(`sig_${r.hiring_signal}` as "sig_yes")}</Badge>}</td>
                  <td className="px-5 py-3 sm:px-6"><Badge tone={reviewTone[r.review_status]}>{t(`rv_${r.review_status}`)}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
