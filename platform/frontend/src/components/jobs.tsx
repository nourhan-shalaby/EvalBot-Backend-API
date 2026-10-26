import { Banknote, Building2, CalendarClock, MapPin, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { PublicJob } from "../lib/api";
import { trackName, useI18n } from "../lib/i18n";
import { Badge, fmtDate, useCatalog } from "./ui";

export function Chip({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 text-sm text-muted">{icon}{children}</span>;
}

/** Location, work mode, job type, salary and deadline as a row of small facts. */
export function JobFacts({ job, showDeadline = true }: { job: Pick<PublicJob, "location" | "work_mode" | "employment_type" | "salary" | "deadline">; showDeadline?: boolean }) {
  const { t, lang } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {job.location && <Chip icon={<MapPin size={15} />}>{job.location}</Chip>}
      <Badge tone="info">{t(`wm_${job.work_mode}` as "wm_onsite")}</Badge>
      <Badge>{t(`et_${job.employment_type}` as "et_full_time")}</Badge>
      {job.salary && <Chip icon={<Banknote size={15} />}>{job.salary}</Chip>}
      {showDeadline && job.deadline && <Chip icon={<CalendarClock size={15} />}>{t("deadline", { d: fmtDate(job.deadline, lang) })}</Chip>}
    </div>
  );
}

export function Skills({ skills }: { skills: string[] }) {
  if (!skills?.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {skills.map((s) => <li key={s} className="ltr rounded-lg border border-line px-2 py-0.5 text-sm text-ink">{s}</li>)}
    </ul>
  );
}

export function CompanyMark({ name, size = 44 }: { name: string; size?: number }) {
  const initials = name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <span className="flex flex-none items-center justify-center rounded-xl bg-nile-soft font-display font-semibold text-nile-deep"
      style={{ width: size, height: size, fontSize: size * 0.36 }} aria-hidden="true">
      {initials || <Building2 size={size * 0.45} />}
    </span>
  );
}

export function JobCard({ job, applied }: { job: PublicJob; applied?: boolean }) {
  const { t, lang } = useI18n();
  const catalog = useCatalog();
  return (
    <li>
      <Link to={`/apply/${job.share_token}`}
        className="group flex gap-4 rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-nile">
        <CompanyMark name={job.company} />
        <div className="min-w-0 flex-1 space-y-2.5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="text-lg font-semibold text-ink group-hover:text-nile">{job.title}</h3>
              <p className="text-[15px] text-muted">
                {job.company}{job.industry ? `, ${job.industry}` : ""} · {trackName(catalog?.tracks, job.track, lang)} · {t(`lv_${job.level}` as "lv_junior")}
              </p>
            </div>
            {applied && <Badge tone="good">{t("applied")}</Badge>}
          </div>
          <JobFacts job={job} />
          {job.snippet && <p className="line-clamp-2 text-[15px] text-ink/85">{job.snippet}</p>}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Skills skills={job.skills.slice(0, 6)} />
            <span className="flex items-center gap-3 text-sm text-muted">
              {!!job.applicants && <Chip icon={<Users size={14} />}>{t("n_applicants", { n: job.applicants })}</Chip>}
              {t("posted", { d: fmtDate(job.created_at, lang) })}
            </span>
          </div>
        </div>
      </Link>
    </li>
  );
}
