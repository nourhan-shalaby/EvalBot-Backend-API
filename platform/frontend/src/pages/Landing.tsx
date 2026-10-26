import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { JobCard } from "../components/jobs";
import { PublicHeader } from "../components/Shell";
import { Waveform, useCatalog } from "../components/ui";
import { api, type PublicJob } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Card = { traits: { trait: string; label: string; model_r: number; human_r: number }[]; reference?: { interviews: number } };

function LiveInterview() {
  const { t } = useI18n();
  return (
    <div className="rise relative rounded-3xl border border-line bg-surface p-5 sm:p-6" aria-label="Example of a practice interview">
      <div className="flex items-center gap-2 text-sm text-muted">
        <span className="pulse-dot inline-block h-2 w-2 rounded-full bg-nile" /> {t("demo_asking")}
      </div>
      <p className="ltr mt-3 font-display text-lg font-medium text-ink sm:text-xl" dir="ltr">{t("demo_question")}</p>
      <div className="mt-6 rounded-2xl bg-sunken p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-ink">{t("demo_you")}</span>
          <span className="flex items-center gap-1.5 text-danger"><span className="pulse-dot h-2 w-2 rounded-full bg-danger" />{t("demo_listening")}</span>
        </div>
        <div className="mt-3 h-14"><Waveform animated bars={40} /></div>
        <p className="ltr mt-3 text-sm text-muted" dir="ltr">{t("demo_answer")}</p>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-3">
        {[[t("demo_content"), 8.1], [t("demo_delivery"), 7.4], [t("demo_structure"), 6.2]].map(([k, v]) => (
          <div key={k as string}>
            <div className="text-xs text-muted">{k}</div>
            <div className="font-display text-2xl font-semibold tabular text-ink">{v}<span className="text-sm text-muted">/10</span></div>
            <div className="mt-1 h-1.5 rounded-full bg-sunken"><div className="h-full rounded-full bg-amber" style={{ width: `${(v as number) * 10}%` }} /></div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Landing() {
  const { t, lang } = useI18n();
  const catalog = useCatalog();
  const [card, setCard] = useState<Card | null>(null);
  const [jobs, setJobs] = useState<PublicJob[]>([]);
  useEffect(() => {
    api.get<PublicJob[]>("/board").then((j) => setJobs(j.slice(0, 4))).catch(() => undefined);
  }, []);
  useEffect(() => {
    api.get<Card>(`/model-card?lang=${lang}`).then(setCard).catch(() => setCard(null));
  }, [lang]);
  const chart = (card?.traits ?? []).filter((x) => ["RecommendHiring", "Overall", "Excited", "EngagingTone", "Friendly", "NoFillers", "StructuredAnswers", "Engaged"].includes(x.trait));

  const feature = (title: string, body: string) => (
    <div className="border-t border-line pt-4">
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      <p className="mt-1.5 text-[15px] text-muted">{body}</p>
    </div>
  );

  return (
    <div className="min-h-screen">
      <PublicHeader />
      <main>
        {/* hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-16 pt-6 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pb-24 lg:pt-14">
          <div>
            <h1 className="max-w-xl text-4xl font-semibold text-ink sm:text-5xl lg:text-[3.4rem]">{t("hero_title")}</h1>
            <p className="mt-5 max-w-xl text-lg text-muted">{t("hero_sub")}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/signup" className="rounded-xl bg-nile px-6 py-3.5 font-medium text-white hover:bg-nile-deep dark:text-paper">{t("cta_candidate")}</Link>
              <Link to="/signup?as=company" className="rounded-xl border border-line bg-surface px-6 py-3.5 font-medium text-ink hover:border-nile hover:text-nile">{t("cta_company")}</Link>
            </div>
          </div>
          <LiveInterview />
        </section>

        {/* how it works: a real sequence */}
        <section className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
            <h2 className="text-2xl font-semibold text-ink">{t("how_title")}</h2>
            <ol className="mt-6 grid gap-6 sm:grid-cols-3">
              {[t("how_1"), t("how_2"), t("how_3")].map((s, i) => (
                <li key={i} className="flex gap-4">
                  <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-nile-soft font-display font-semibold text-nile-deep">{i + 1}</span>
                  <p className="pt-1 text-[15px] text-ink">{s}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* two audiences */}
        <section className="mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-semibold text-ink">{t("for_candidates")}</h2>
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              {feature(t("c1_t"), t("c1_d"))}{feature(t("c2_t"), t("c2_d"))}{feature(t("c3_t"), t("c3_d"))}{feature(t("c4_t"), t("c4_d"))}
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-semibold text-ink">{t("for_companies")}</h2>
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              {feature(t("r1_t"), t("r1_d"))}{feature(t("r2_t"), t("r2_d"))}{feature(t("r3_t"), t("r3_d"))}{feature(t("r4_t"), t("r4_d"))}
            </div>
          </div>
        </section>

        {/* open roles from companies on the platform */}
        {jobs.length > 0 && (
          <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
            <div className="mb-5 flex items-end justify-between gap-3">
              <h2 className="text-2xl font-semibold text-ink">{t("open_roles")}</h2>
              <Link to="/jobs" className="font-medium text-nile hover:underline">{t("see_all_jobs")}</Link>
            </div>
            <ul className="grid gap-3 lg:grid-cols-2">{jobs.map((j) => <JobCard key={j.id} job={j} />)}</ul>
          </section>
        )}

        {/* science */}
        {chart.length > 0 && (
          <section className="bg-ink text-paper dark:bg-surface dark:text-ink">
            <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_1.3fr]">
              <div>
                <h2 className="text-3xl font-semibold">{t("science_title")}</h2>
                <p className="mt-4 text-[17px] opacity-80">{t("science_text")}</p>
                <p className="mt-4 text-sm opacity-60">{t("science_note")}</p>
              </div>
              <div className="h-80 rounded-2xl bg-surface p-4 text-ink" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart} layout="vertical" margin={{ left: 10, right: 16, top: 4, bottom: 4 }} barGap={2}>
                    <CartesianGrid horizontal={false} stroke="var(--color-line)" />
                    <XAxis type="number" domain={[0, 1]} tickCount={6} stroke="var(--color-muted)" fontSize={12} />
                    <YAxis type="category" dataKey="label" width={lang === "ar" ? 120 : 150} stroke="var(--color-muted)" fontSize={12}
                      tick={{ fill: "var(--color-ink)" }} />
                    <Tooltip cursor={{ fill: "var(--color-sunken)" }} contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-line)", borderRadius: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="model_r" name={t("science_model")} fill="var(--color-nile)" radius={[0, 4, 4, 0]} />
                    <Bar dataKey="human_r" name={t("science_human")} fill="var(--color-amber)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        )}

        {/* tracks */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-semibold text-ink">{t("tracks_title")}</h2>
          <div className="mt-6 flex flex-wrap gap-2">
            {catalog?.tracks.map((tr) => (
              <span key={tr.id} className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-sm text-ink">{lang === "ar" ? tr.ar : tr.en}</span>
            ))}
          </div>
          <div className="mt-12 flex flex-col items-start gap-4 rounded-3xl bg-nile-soft p-8 sm:flex-row sm:items-center sm:justify-between">
            <div className="h-12 w-48"><Waveform bars={30} color="var(--color-nile)" /></div>
            <Link to="/signup" className="rounded-xl bg-nile px-6 py-3.5 font-medium text-white hover:bg-nile-deep dark:text-paper">{t("cta_candidate")}</Link>
          </div>
        </section>
      </main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-muted sm:px-6">
          <p>{t("footer_text")}</p>
          <p>{t("footer_privacy")}</p>
        </div>
      </footer>
    </div>
  );
}
