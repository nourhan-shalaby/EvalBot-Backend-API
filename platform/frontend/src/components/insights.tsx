import { AlertTriangle, Briefcase, CheckCircle2, GraduationCap, Languages, Play, ShieldAlert, ShieldCheck, Video } from "lucide-react";
import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type CameraInfo, type CvProfile, type EmotionProbs, type Integrity, type Report, type SkillMatch } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { fmtClock } from "../lib/media";
import { Badge, Meter, Panel } from "./ui";

export const EMO_ORDER: (keyof EmotionProbs)[] = ["neutral", "happy", "surprised", "sad", "angry", "fearful", "disgusted"];
export const EMO_COLOR: Record<keyof EmotionProbs, string> = {
  neutral: "#8FA3A0", happy: "var(--color-nile)", surprised: "var(--color-amber)", sad: "#5B7DB1",
  angry: "var(--color-danger)", fearful: "#8E6BB8", disgusted: "#9A7B4F",
};
const tip = { background: "var(--color-surface)", border: "1px solid var(--color-line)", borderRadius: 12, color: "var(--color-ink)" };
const pct = (v: number | null | undefined) => `${Math.round((v ?? 0) * 100)}%`;

/** Plays an answer recording; video answers get a video player. */
export function AnswerMedia({ sid, idx, video }: { sid: string; idx: number; video?: boolean }) {
  const { t } = useI18n();
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  if (url)
    return video ? <video src={url} controls autoPlay playsInline className="aspect-video w-full rounded-xl bg-ink" />
      : <audio src={url} controls autoPlay className="h-10 w-full" />;
  return (
    <button onClick={async () => { setBusy(true); try { setUrl(URL.createObjectURL(await api.blob(`/sessions/${sid}/answers/${idx}/audio`))); } finally { setBusy(false); } }}
      className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm text-ink hover:border-nile hover:text-nile" disabled={busy}>
      {video ? <Video size={14} /> : <Play size={14} />} {busy ? "…" : t("play")}
    </button>
  );
}

export function EmotionBars({ probs }: { probs: EmotionProbs }) {
  const { t } = useI18n();
  const rows = EMO_ORDER.map((e) => [e, probs[e] ?? 0] as const).sort((a, b) => b[1] - a[1]);
  return (
    <ul className="space-y-2.5">
      {rows.map(([e, v]) => (
        <li key={e} className="grid grid-cols-[6.5rem_1fr_3rem] items-center gap-3 text-sm">
          <span className="text-ink">{t(`emo_${e}`)}</span>
          <div className="h-2.5 overflow-hidden rounded-full bg-sunken"><div className="h-full rounded-full" style={{ width: `${Math.max(1.5, v * 100)}%`, background: EMO_COLOR[e] }} /></div>
          <span className="text-end tabular text-muted">{pct(v)}</span>
        </li>
      ))}
    </ul>
  );
}

export function CameraPanel({ cam, nonverbal, self, dir }: { cam: CameraInfo; nonverbal?: string; self: boolean; dir: string }) {
  const { t } = useI18n();
  const data = cam.timeline.map((x) => ({ label: `Q${x.answer} ${fmtClock(x.t)}`, ...x.probs }));
  return (
    <Panel title={t("cam_title")}>
      <p className="-mt-2 mb-5 text-sm text-muted">{self ? t("cam_sub_self") : t("cam_sub")}</p>
      <div className="grid grid-cols-3 gap-3">
        {[[t("eye_contact"), cam.eye_contact], [t("face_visible"), cam.face_visible], [t("smile"), cam.smile]].map(([l, v]) => (
          <div key={l as string} className="rounded-xl bg-sunken p-3">
            <p className="text-xs text-muted">{l}</p>
            <p className="font-display text-2xl font-semibold tabular text-ink">{pct(v as number)}</p>
          </div>
        ))}
      </div>
      {cam.emotions && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <div>
            <p className="mb-3 flex flex-wrap items-baseline justify-between gap-2 font-medium text-ink">
              {t("expressions")}
              {cam.dominant_emotion && <span className="text-sm font-normal text-muted">{t("dominant")}: {t(`emo_${cam.dominant_emotion}`)}</span>}
            </p>
            <EmotionBars probs={cam.emotions} />
          </div>
          {data.length > 1 && (
            <div>
              <p className="mb-3 font-medium text-ink">{t("expr_timeline")}</p>
              <div className="h-52" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data} margin={{ left: -22, right: 4, top: 4 }} stackOffset="expand">
                    <CartesianGrid stroke="var(--color-line)" vertical={false} />
                    <XAxis dataKey="label" stroke="var(--color-muted)" fontSize={10} interval="preserveStartEnd" />
                    <YAxis stroke="var(--color-muted)" fontSize={11} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                    <Tooltip contentStyle={tip} formatter={(v: number, k: string) => [`${Math.round(v * 100)}%`, t(`emo_${k}` as "emo_happy")]} />
                    {EMO_ORDER.map((e) => <Area key={e} type="monotone" dataKey={e} stackId="1" stroke={EMO_COLOR[e]} fill={EMO_COLOR[e]} fillOpacity={0.75} />)}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
                {EMO_ORDER.map((e) => <li key={e} className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: EMO_COLOR[e] }} />{t(`emo_${e}`)}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
      {nonverbal && <p className="mt-6 rounded-xl bg-sunken p-4 text-[15px] text-ink" dir={dir}><span className="font-medium">{t("nonverbal")}: </span>{nonverbal}</p>}
    </Panel>
  );
}

export function IntegrityPanel({ integ, self }: { integ: Integrity; self: boolean }) {
  const { t } = useI18n();
  const tone = integ.level === "low" ? "good" : integ.level === "medium" ? "warn" : "bad";
  const Icon = integ.level === "low" ? ShieldCheck : ShieldAlert;
  const color = integ.level === "low" ? "var(--color-nile)" : integ.level === "medium" ? "var(--color-amber)" : "var(--color-danger)";
  const counts = Object.entries(integ.counts).sort((a, b) => b[1] - a[1]);
  return (
    <Panel title={self ? t("integrity_self") : t("integrity_title")}>
      <p className="-mt-2 mb-5 text-sm text-muted">{self ? t("integrity_self_sub") : t("integrity_sub")}</p>
      <div className="flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-3">
          <Icon size={36} style={{ color }} />
          <div>
            <p className="text-xs text-muted">{t("integrity_score")}</p>
            <p className="font-display text-3xl font-semibold tabular" style={{ color }}>{integ.score}<span className="text-base text-muted">/100</span></p>
          </div>
        </div>
        {!self && <div><p className="text-xs text-muted">{t("priority")}</p><Badge tone={tone}>{t(`pr_${integ.level}`)}</Badge></div>}
        {!integ.camera && <Badge>{t("camera_was_off")}</Badge>}
      </div>
      {counts.length === 0 ? (
        <p className="mt-5 flex items-center gap-2 text-[15px] text-ink"><CheckCircle2 size={18} className="text-nile" /> {t("no_flags")}</p>
      ) : (
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <ul className="space-y-2">
            {counts.map(([k, n]) => (
              <li key={k} className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2 text-[15px]">
                <span className="flex items-center gap-2 text-ink"><AlertTriangle size={16} className="text-amber" />{t(`fl_${k}` as "fl_no_face")}</span>
                <span className="tabular text-muted">×{n}</span>
              </li>
            ))}
          </ul>
          <ol className="max-h-60 space-y-1.5 overflow-auto text-sm">
            {integ.events.map((e, i) => (
              <li key={i} className="flex justify-between gap-3 border-b border-line pb-1.5 last:border-0">
                <span className="text-ink">{t(`fl_${e.type}` as "fl_no_face")}</span>
                <span className="whitespace-nowrap tabular text-muted">{t("flag_at", { q: e.answer ?? "?", t: fmtClock(e.t) })}{e.dur ? ` · ${Math.round(e.dur)}s` : ""}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Panel>
  );
}

export function SkillsPanel({ r, dir }: { r: Report; dir: string }) {
  const { t } = useI18n();
  const soft = r.summary?.soft_skills ?? [];
  const rub = r.rubric ?? ({} as Record<string, number | null>);
  const rubRows = (["clarity", "example_quality", "structure", "outcome"] as const).filter((k) => rub[k] != null);
  if (!soft.length && !rubRows.length) return null;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {!!rubRows.length && (
        <Panel title={t("rubric_title")}>
          <ul className="space-y-3">
            {rubRows.map((k) => (
              <li key={k}>
                <div className="mb-1 flex justify-between text-sm"><span className="text-ink">{t(`rb_${k}`)}</span><span className="tabular text-muted">{rub[k]}/10</span></div>
                <Meter value={rub[k] as number} max={10} />
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {!!soft.length && (
        <Panel title={t("soft_title")}>
          <ul className="space-y-3.5">
            {soft.map((x) => (
              <li key={x.skill}>
                <div className="mb-1 flex justify-between text-sm"><span className="font-medium text-ink">{t(`ss_${x.skill}` as "ss_teamwork")}</span><span className="tabular text-muted">{x.score}/10</span></div>
                <Meter value={x.score} max={10} />
                {x.comment && <p className="mt-1 text-sm text-muted" dir={dir}>{x.comment}</p>}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

export function CvView({ cv, match, compact = false }: { cv: CvProfile; match?: SkillMatch | null; compact?: boolean }) {
  const { t } = useI18n();
  const matched = new Set((match?.matched ?? []).map((x) => x.toLowerCase()));
  return (
    <div className="space-y-5">
      <div>
        <p className="text-lg font-semibold text-ink">{cv.name}</p>
        {cv.headline && <p className="text-[15px] text-muted">{cv.headline}</p>}
        {!!cv.years_experience && <p className="mt-1 text-sm text-muted">{t("cv_years", { n: cv.years_experience })}</p>}
      </div>
      {match && (
        <div className="rounded-xl bg-sunken p-4">
          <div className="mb-1.5 flex justify-between text-sm"><span className="font-medium text-ink">{t("cv_match", { p: match.percent })}</span></div>
          <Meter value={match.percent} />
          {!!match.missing.length && <p className="mt-2 text-sm text-muted">{t("cv_missing")}: <span className="ltr" dir="ltr">{match.missing.join(", ")}</span></p>}
        </div>
      )}
      {!!cv.skills.length && (
        <div>
          <p className="mb-2 text-sm font-medium text-muted">{t("cv_skills")}</p>
          <ul className="flex flex-wrap gap-1.5" dir="ltr">
            {cv.skills.map((s) => (
              <li key={s} className={`rounded-lg border px-2 py-0.5 text-sm ${matched.has(s.toLowerCase()) ? "border-nile bg-nile-soft text-nile-deep" : "border-line text-ink"}`}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {!!cv.experience.length && (
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted"><Briefcase size={15} /> {t("cv_experience")}</p>
          <ul className="space-y-3">
            {cv.experience.slice(0, compact ? 3 : 20).map((x, i) => (
              <li key={i}><p className="font-medium text-ink">{x.title}{x.company ? `, ${x.company}` : ""}</p>
                <p className="text-xs text-muted">{x.period}</p>{!compact && <p className="mt-0.5 text-sm text-ink">{x.summary}</p>}</li>
            ))}
          </ul>
        </div>
      )}
      {!!cv.projects.length && !compact && (
        <div>
          <p className="mb-2 text-sm font-medium text-muted">{t("cv_projects")}</p>
          <ul className="space-y-3">{cv.projects.map((x, i) => (
            <li key={i}><p className="font-medium text-ink">{x.name}</p><p className="text-sm text-ink">{x.summary}</p>
              {!!x.tech.length && <p className="ltr mt-0.5 text-xs text-muted" dir="ltr">{x.tech.join(" · ")}</p>}</li>))}</ul>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {!!cv.education.length && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted"><GraduationCap size={15} /> {t("cv_education")}</p>
            <ul className="space-y-1.5 text-sm text-ink">{cv.education.map((x, i) => <li key={i}>{x.degree}, {x.institution}{x.year ? ` (${x.year})` : ""}</li>)}</ul>
          </div>
        )}
        {(!!cv.languages.length || !!cv.certifications.length) && (
          <div className="space-y-3">
            {!!cv.languages.length && <p className="flex items-center gap-1.5 text-sm text-ink"><Languages size={15} className="text-muted" /> {cv.languages.join(", ")}</p>}
            {!!cv.certifications.length && <div><p className="mb-1 text-sm font-medium text-muted">{t("cv_certs")}</p>
              <ul className="list-disc space-y-0.5 ps-5 text-sm text-ink">{cv.certifications.map((x, i) => <li key={i}>{x}</li>)}</ul></div>}
          </div>
        )}
      </div>
    </div>
  );
}
