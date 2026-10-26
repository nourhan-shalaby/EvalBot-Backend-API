import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Meter, Panel, Spinner, Waveform } from "../components/ui";
import { api, type SessionRow } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import CompanyDashboard from "./CompanyDashboard";
import { SessionList } from "./History";

type Stats = {
  interviews: number; answers: number; speaking_minutes: number; average: number | null; best: number | null;
  trend: { date: string; score: number; track: string }[]; skills: { skill: string; avg: number; n: number }[];
};

export default function Dashboard() {
  const { profile } = useAuth();
  return profile?.role === "recruiter" ? <CompanyDashboard /> : <CandidateDashboard />;
}

function CandidateDashboard() {
  const { t } = useI18n();
  const { profile } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [rows, setRows] = useState<SessionRow[] | null>(null);
  useEffect(() => {
    api.get<Stats>("/stats").then(setStats).catch(() => undefined);
    api.get<SessionRow[]>("/sessions").then(setRows).catch(() => setRows([]));
  }, []);
  if (!stats || !rows) return <Spinner />;
  const first = (profile?.full_name || "").split(" ")[0] || "";
  const tile = (label: string, value: string | number | null) => (
    <div className="rounded-2xl border border-line bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-display text-3xl font-semibold tabular text-ink">{value ?? "–"}</p>
    </div>
  );
  const skills = [...stats.skills].sort((a, b) => b.avg - a.avg);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-3xl bg-nile p-6 text-white sm:flex-row sm:items-center sm:justify-between sm:p-8 dark:text-paper">
        <div>
          <h1 className="text-3xl font-semibold">{first ? t("hello", { name: first }) : t("dash_sub")}</h1>
          {first && <p className="mt-1 opacity-85">{t("dash_sub")}</p>}
        </div>
        <div className="flex items-center gap-5">
          <div className="hidden h-12 w-36 md:block"><Waveform bars={22} color="var(--color-amber)" /></div>
          <Link to="/app/board" className="rounded-xl border border-white/40 px-5 py-3 font-medium hover:bg-white/10">{t("browse_jobs")}</Link>
          <Link to="/app/new" className="rounded-xl bg-white px-5 py-3 font-medium text-nile-deep hover:bg-amber-soft dark:bg-paper">{t("nav_new")}</Link>
        </div>
      </div>

      {stats.interviews === 0 && rows.length === 0 ? (
        <Panel><p className="text-muted">{t("empty_dash")}</p></Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {tile(t("stat_interviews"), stats.interviews)}
            {tile(t("stat_average"), stats.average)}
            {tile(t("stat_best"), stats.best)}
            {tile(t("stat_minutes"), stats.speaking_minutes)}
          </div>
          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <Panel title={t("progress_title")}>
              {stats.trend.length > 1 ? (
                <div className="h-56" dir="ltr">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={stats.trend} margin={{ left: -20, right: 8, top: 8 }}>
                      <CartesianGrid stroke="var(--color-line)" vertical={false} />
                      <XAxis dataKey="date" stroke="var(--color-muted)" fontSize={12} />
                      <YAxis domain={[0, 100]} stroke="var(--color-muted)" fontSize={12} />
                      <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-line)", borderRadius: 12 }} />
                      <Line type="monotone" dataKey="score" stroke="var(--color-nile)" strokeWidth={2.5} dot={{ r: 4, fill: "var(--color-nile)" }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-sm text-muted">{stats.trend.length === 1 ? `${stats.trend[0].score}` : "–"}</p>
              )}
            </Panel>
            <Panel title={t("skills_title")}>
              {skills.length ? (
                <ul className="space-y-3">
                  {skills.map((s) => (
                    <li key={s.skill}>
                      <div className="mb-1 flex justify-between gap-2 text-sm"><span className="ltr truncate text-ink">{s.skill}</span><span className="tabular text-muted">{s.avg}/10</span></div>
                      <Meter value={s.avg} max={10} />
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted">–</p>}
            </Panel>
          </div>
          <div>
            <h2 className="mb-3 text-lg font-semibold text-ink">{t("recent")}</h2>
            <SessionList rows={rows.slice(0, 6)} />
          </div>
        </>
      )}
    </div>
  );
}
