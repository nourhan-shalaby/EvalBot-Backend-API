import { Link2, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { Badge, Spinner, fmtDate, useCatalog } from "../components/ui";
import { api, type Job } from "../lib/api";
import { useAuth } from "../lib/auth";
import { trackName, useI18n } from "../lib/i18n";

export function CopyLink({ token }: { token: string }) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  const url = `${location.origin}/apply/${token}`;
  return (
    <button onClick={async () => { await navigator.clipboard.writeText(url).catch(() => undefined); setDone(true); setTimeout(() => setDone(false), 2000); }}
      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-nile hover:bg-nile-soft">
      <Link2 size={15} /> {done ? t("link_copied") : t("copy_link")}
    </button>
  );
}

export default function Jobs() {
  const { t, lang } = useI18n();
  const { profile } = useAuth();
  const catalog = useCatalog();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  useEffect(() => {
    if (profile?.company_id) api.get<Job[]>("/jobs").then(setJobs).catch(() => setJobs([]));
  }, [profile]);
  if (profile && !profile.company_id) return <Navigate to="/app/welcome?as=company" replace />;
  if (!jobs) return <Spinner />;
  const tone = { open: "good", draft: "neutral", closed: "bad" } as const;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold text-ink">{t("jobs_title")}</h1>
          {profile?.company && <p className="text-muted">{profile.company.name}</p>}
        </div>
        <Link to="/app/jobs/new" className="inline-flex items-center gap-2 rounded-xl bg-nile px-4 py-2.5 text-sm font-medium text-white dark:text-paper"><Plus size={16} /> {t("new_job")}</Link>
      </div>
      {jobs.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line p-8 text-center text-muted">{t("empty_jobs")}</p>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
          {jobs.map((j) => (
            <li key={j.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
              <Link to={`/app/jobs/${j.id}`} className="min-w-0 flex-1">
                <p className="truncate font-medium text-ink">{j.title}</p>
                <p className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-muted">
                  <span>{trackName(catalog?.tracks, j.track, lang)}</span>
                  <Badge tone={tone[j.status]}>{t(`jst_${j.status}`)}</Badge>
                  <span>{fmtDate(j.created_at, lang)}</span>
                </p>
              </Link>
              <div className="flex items-center gap-6">
                <div className="text-center"><p className="font-display text-xl font-semibold tabular text-ink">{j.applicants ?? 0}</p><p className="text-xs text-muted">{t("applicants")}</p></div>
                <div className="text-center"><p className="font-display text-xl font-semibold tabular text-ink">{j.completed ?? 0}</p><p className="text-xs text-muted">{t("completed_n")}</p></div>
                <CopyLink token={j.share_token} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
