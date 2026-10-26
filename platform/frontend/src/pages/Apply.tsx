import { Clock, ListChecks, Mic } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PublicHeader } from "../components/Shell";
import { Button, ErrorNote, Spinner, Waveform } from "../components/ui";
import { api, type Session } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type PublicJob = { id: string; title: string; company: string; description: string | null; answer_seconds: number; status: string; question_count: number };

export default function Apply() {
  const { token } = useParams();
  const { t, lang } = useI18n();
  const { profile, ready } = useAuth();
  const nav = useNavigate();
  const [job, setJob] = useState<PublicJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    api.get<PublicJob>(`/public/jobs/${token}`).then(setJob).catch((e) => setError(e.message));
  }, [token]);

  const start = async () => {
    setBusy(true);
    try {
      const s = await api.post<Session>(`/jobs/apply/${token}`, { language: lang });
      if (s.status === "in_progress") nav(`/app/interview/${s.id}`);
      else setDone(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen">
      <PublicHeader />
      <main className="mx-auto max-w-2xl px-4 pb-16 pt-8">
        {error ? <ErrorNote>{error}</ErrorNote> : !job || !ready ? <Spinner /> : (
          <div className="rounded-3xl border border-line bg-surface p-6 sm:p-10">
            <div className="h-10 w-40"><Waveform bars={20} color="var(--color-nile)" /></div>
            <h1 className="mt-6 text-3xl font-semibold text-ink">{t("apply_title", { company: job.company })}</h1>
            <p className="mt-1 text-xl text-muted">{t("apply_for", { title: job.title })}</p>
            {job.description && <p className="mt-6 whitespace-pre-line text-[15px] text-ink">{job.description}</p>}
            <ul className="mt-6 space-y-2 text-[15px] text-ink">
              <li className="flex items-center gap-3"><ListChecks size={18} className="text-nile" /> {t("apply_q", { n: job.question_count })}</li>
              <li className="flex items-center gap-3"><Clock size={18} className="text-nile" /> {t("apply_time", { m: Math.round(job.answer_seconds / 60) })}</li>
              <li className="flex items-start gap-3"><Mic size={18} className="mt-0.5 flex-none text-nile" /> {t("apply_how")}</li>
            </ul>
            <div className="mt-8">
              {job.status !== "open" ? <p className="text-muted">{t("apply_closed")}</p>
                : done ? <p className="rounded-xl bg-nile-soft px-4 py-3 text-nile-deep">{t("apply_done")}</p>
                : profile ? <Button size="lg" onClick={start} busy={busy}>{t("apply_start")}</Button>
                : <Link to={`/signup?next=${encodeURIComponent(`/apply/${token}`)}`} className="inline-block rounded-xl bg-nile px-6 py-3.5 font-medium text-white dark:text-paper">{t("apply_signin")}</Link>}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
