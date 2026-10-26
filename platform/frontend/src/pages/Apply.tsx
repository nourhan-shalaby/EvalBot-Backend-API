import { ArrowLeft, Clock, Globe, ListChecks, Mic } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CompanyMark, JobFacts, Skills } from "../components/jobs";
import { AppShell, PublicHeader } from "../components/Shell";
import { Button, ErrorNote, Spinner, fmtDate, useCatalog } from "../components/ui";
import { api, type Application, type PublicJob, type Session } from "../lib/api";
import { useAuth } from "../lib/auth";
import { trackName, useI18n } from "../lib/i18n";

export default function Apply() {
  const { token } = useParams();
  const { t, lang } = useI18n();
  const { profile, ready } = useAuth();
  const catalog = useCatalog();
  const nav = useNavigate();
  const [job, setJob] = useState<PublicJob | null>(null);
  const [mine, setMine] = useState<Application | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<PublicJob>(`/public/jobs/${token}`).then(setJob).catch((e) => setError(e.message));
  }, [token]);
  useEffect(() => {
    if (!ready) return;
    if (profile?.role === "candidate") api.get<Application[]>("/applications").then((a) => setMine(a.find((x) => x.share_token === token) ?? null)).catch(() => setMine(null));
    else setMine(null);
  }, [ready, profile, token]);

  const start = async () => {
    setBusy(true);
    try {
      const s = await api.post<Session>(`/jobs/apply/${token}`, { language: lang });
      nav(s.status === "in_progress" ? `/app/interview/${s.id}` : `/app/applications`);
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };

  const action = () => {
    if (!job) return null;
    if (profile?.role === "recruiter") return <p className="rounded-xl bg-amber-soft px-4 py-3 text-ink">{t("company_cant_apply")}</p>;
    if (mine?.status === "in_progress") return <Link to={`/app/interview/${mine.id}`} className="inline-block rounded-xl bg-nile px-6 py-3.5 font-medium text-white dark:text-paper">{t("finish_interview")}</Link>;
    if (mine) return <p className="rounded-xl bg-nile-soft px-4 py-3 text-nile-deep">{t("apply_done")} <Link to="/app/applications" className="font-medium underline">{t("nav_applications")}</Link></p>;
    if (!job.accepting) return <p className="text-muted">{t("apply_closed")}</p>;
    if (profile) return <Button size="lg" onClick={start} busy={busy}>{t("apply_start")}</Button>;
    return <Link to={`/signup?next=${encodeURIComponent(`/apply/${token}`)}`} className="inline-block rounded-xl bg-nile px-6 py-3.5 font-medium text-white dark:text-paper">{t("apply_signin")}</Link>;
  };

  const content = error && !job ? <ErrorNote>{error}</ErrorNote> : !job || !ready || mine === undefined ? <Spinner /> : (
    <div className="space-y-6">
      {profile?.role === "candidate" && (
        <Link to="/app/board" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"><ArrowLeft size={16} className="rtl:rotate-180" /> {t("nav_board")}</Link>
      )}
      <div className="rounded-3xl border border-line bg-surface p-6 sm:p-10">
        <div className="flex items-start gap-4">
          <CompanyMark name={job.company} size={56} />
          <div className="min-w-0">
            <h1 className="text-3xl font-semibold text-ink">{job.title}</h1>
            <p className="mt-1 text-lg text-muted">{job.company} · {trackName(catalog?.tracks, job.track, lang)} · {t(`lv_${job.level}` as "lv_junior")}</p>
          </div>
        </div>
        <div className="mt-6 space-y-3">
          <JobFacts job={job} />
          <Skills skills={job.skills} />
          <p className="text-sm text-muted">{t("posted", { d: fmtDate(job.created_at, lang) })}</p>
        </div>
        {job.description && <p className="mt-6 whitespace-pre-line text-[15px] leading-relaxed text-ink">{job.description}</p>}

        <div className="mt-8 rounded-2xl bg-sunken p-5">
          <p className="font-semibold text-ink">{t("apply_title", { company: job.company })}</p>
          <ul className="mt-3 space-y-2 text-[15px] text-ink">
            <li className="flex items-center gap-3"><ListChecks size={18} className="text-nile" /> {t("apply_q", { n: job.question_count })}</li>
            <li className="flex items-center gap-3"><Clock size={18} className="text-nile" /> {t("apply_time", { m: Math.round(job.answer_seconds / 60) })}</li>
            <li className="flex items-start gap-3"><Mic size={18} className="mt-0.5 flex-none text-nile" /> {t("apply_how")}</li>
          </ul>
          <div className="mt-6">{action()}</div>
          {error && <div className="mt-4"><ErrorNote>{error}</ErrorNote></div>}
        </div>
      </div>
      {(job.company_about || job.industry || job.company_location) && (
        <div className="rounded-3xl border border-line bg-surface p-6 sm:p-8">
          <h2 className="text-lg font-semibold text-ink">{t("about_company", { company: job.company })}</h2>
          <p className="mt-1 text-sm text-muted">{[job.industry, job.company_size && `${job.company_size}`, job.company_location].filter(Boolean).join(" · ")}</p>
          {job.company_about && <p className="mt-3 whitespace-pre-line text-[15px] text-ink">{job.company_about}</p>}
          {job.website && <a href={job.website} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-sm text-nile hover:underline"><Globe size={15} /> {job.website.replace(/^https?:\/\//, "")}</a>}
        </div>
      )}
    </div>
  );

  if (profile?.role === "candidate") return <AppShell>{content}</AppShell>;
  return (
    <div className="min-h-screen">
      <PublicHeader />
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">{content}</main>
    </div>
  );
}
