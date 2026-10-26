import { ChevronDown, Download, Play, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Button, ErrorNote, Field, Meter, Panel, ScoreRing, Spinner, Textarea, Waveform, fmtDate, scoreColor, useCatalog } from "../components/ui";
import { api, type Answer, type Session } from "../lib/api";
import { useAuth } from "../lib/auth";
import { trackName, useI18n } from "../lib/i18n";

function AnswerAudio({ sid, idx }: { sid: string; idx: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  if (url) return <audio src={url} controls autoPlay className="h-10 w-full" />;
  return (
    <button onClick={async () => { setBusy(true); try { setUrl(URL.createObjectURL(await api.blob(`/sessions/${sid}/answers/${idx}/audio`))); } finally { setBusy(false); } }}
      className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm text-ink hover:border-nile hover:text-nile" disabled={busy}>
      <Play size={14} /> {busy ? "…" : "Play"}
    </button>
  );
}

function QuestionCard({ a, sid, open: initial, lang }: { a: Answer; sid: string; open: boolean; lang: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(initial);
  const fb = a.feedback || ({} as NonNullable<Answer["feedback"]>);
  const dir = lang === "ar" ? "rtl" : "ltr";
  const p = a.presence;
  return (
    <div className="rounded-2xl border border-line bg-surface">
      <button onClick={() => setOpen(!open)} className="flex w-full items-start gap-4 p-4 text-start sm:p-5" aria-expanded={open}>
        <span className="flex h-10 w-10 flex-none items-center justify-center rounded-xl font-display font-semibold tabular text-white dark:text-paper"
          style={{ background: scoreColor(a.score, 10) }}>{a.score ?? "–"}</span>
        <span className="min-w-0 flex-1">
          {a.is_followup && <Badge tone="info">{t("followup")}</Badge>}
          <span className="ltr mt-1 block font-medium text-ink" dir="ltr">{a.question}</span>
        </span>
        <ChevronDown size={18} className={`mt-2 flex-none text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-line p-4 sm:p-5">
          <div className="rounded-xl bg-sunken p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium text-muted">{t("your_answer")}</span>
              {a.has_audio && <AnswerAudio sid={sid} idx={a.idx} />}
            </div>
            <p className="ltr text-[15px] text-ink" dir="ltr">{a.transcript || t("not_answered")}</p>
          </div>
          {fb.summary && <p className="text-[15px] text-ink" dir={dir}>{fb.summary}</p>}
          <div className="grid gap-3 md:grid-cols-2">
            {!!fb.strengths?.length && (
              <div className="rounded-xl bg-nile-soft p-4"><p className="mb-1.5 text-sm font-medium text-nile-deep">{t("went_well")}</p>
                <ul className="list-disc space-y-1 ps-5 text-[15px] text-ink" dir={dir}>{fb.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
            )}
            {!!fb.improvements?.length && (
              <div className="rounded-xl bg-amber-soft p-4"><p className="mb-1.5 text-sm font-medium text-ink">{t("improve")}</p>
                <ul className="list-disc space-y-1 ps-5 text-[15px] text-ink" dir={dir}>{fb.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
            )}
          </div>
          {fb.improved_answer && (
            <div className="rounded-xl border border-line p-4"><p className="mb-1.5 text-sm font-medium text-muted">{t("stronger")}</p>
              <p className="ltr text-[15px] text-ink" dir="ltr">{fb.improved_answer}</p></div>
          )}
          <div className="flex flex-wrap gap-2 text-sm text-muted">
            {fb.delivery_tip && <span dir={dir}><span className="font-medium text-ink">{t("delivery_tip")}: </span>{fb.delivery_tip}</span>}
          </div>
          {p && (
            <div className="flex flex-wrap gap-2">
              <Badge>{t("eye_contact")}: {Math.round((p.eye_contact ?? 0) * 100)}%</Badge>
              <Badge>{t("smile")}: {Math.round((p.smile ?? 0) * 100)}%</Badge>
              <Badge>{t("face_visible")}: {Math.round((p.face_visible ?? 0) * 100)}%</Badge>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewPanel({ s }: { s: Session }) {
  const { t } = useI18n();
  const [status, setStatus] = useState("new");
  const [rating, setRating] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!s.job_id) return;
    api.get<any[]>(`/jobs/${s.job_id}/candidates`).then((rows) => {
      const r = rows.find((x) => x.id === s.id);
      if (r) { setStatus(r.review_status); setRating(r.rating); setNotes(r.notes || ""); }
    });
  }, [s]);
  const save = async () => {
    await api.put(`/reviews/${s.id}`, { status, rating, notes });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };
  return (
    <Panel title={t("decision")}>
      <p className="mb-4 text-sm text-muted">{t("fairness")}</p>
      <div className="flex flex-wrap gap-2">
        {(["new", "shortlisted", "rejected", "hired"] as const).map((k) => (
          <button key={k} onClick={() => setStatus(k)} aria-pressed={status === k}
            className={`rounded-xl border px-3.5 py-2 text-sm ${status === k ? "border-nile bg-nile-soft font-medium text-nile-deep" : "border-line text-ink hover:border-nile"}`}>{t(`rv_${k}`)}</button>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-1" aria-label={t("rating")}>
        <span className="me-2 text-sm text-muted">{t("rating")}</span>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => setRating(n)} aria-label={`${n}`} className="p-0.5">
            <Star size={20} className={rating && n <= rating ? "fill-amber text-amber" : "text-line"} />
          </button>
        ))}
      </div>
      <div className="mt-4"><Field label={t("notes")}><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></Field></div>
      <div className="mt-4 flex items-center gap-3"><Button onClick={save}>{t("save_review")}</Button>{saved && <span className="text-sm text-nile">{t("saved")}</span>}</div>
    </Panel>
  );
}

export default function ReportPage() {
  const { id } = useParams();
  const { t, lang, d } = useI18n();
  const level = (k?: string) => (k ? d.lv[k] ?? k : "–");
  const { profile } = useAuth();
  const catalog = useCatalog();
  const [s, setS] = useState<Session | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = useState(false);

  useEffect(() => {
    let timer = 0;
    const load = () => api.get<Session>(`/sessions/${id}`).then((x) => {
      setS(x);
      if (x.status === "processing" || x.status === "in_progress") timer = window.setTimeout(load, 4000);
    }).catch((e) => setError(e.message));
    load();
    return () => window.clearTimeout(timer);
  }, [id]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!s) return <Spinner />;
  if (s.status === "processing" || (s.status === "in_progress" && s.user_id !== profile?.id))
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-24 text-center">
        <div className="h-16 w-64"><Waveform animated bars={30} color="var(--color-nile)" /></div>
        <h1 className="text-2xl font-semibold text-ink">{t("building_title")}</h1>
        <p className="max-w-md text-muted">{t("building_sub")}</p>
      </div>
    );
  if (s.status === "failed" || !s.report) return <ErrorNote>{t("report_failed")} {s.error}</ErrorNote>;

  const r = s.report;
  const sum = r.summary || {};
  const dir = s.language === "ar" ? "rtl" : "ltr";
  const v = r.voice || {};
  const isReviewer = s.user_id !== profile?.id;
  const signal = sum.hiring_signal;
  const title = s.job?.title || s.context.role || trackName(catalog?.tracks, s.track, lang);
  const humanR = r.calibrated?.traits.find((x) => x.trait === "Overall")?.human_r ?? 0.5;

  const downloadPdf = async () => {
    setPdfBusy(true);
    try {
      const b = await api.blob(`/sessions/${s.id}/pdf`);
      const url = URL.createObjectURL(b);
      const a = document.createElement("a");
      a.href = url;
      a.download = `evalbot-report-${s.id.slice(0, 8)}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } finally {
      setPdfBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex flex-col gap-6 rounded-3xl border border-line bg-surface p-6 sm:flex-row sm:items-center sm:p-8">
        <ScoreRing value={r.overall} size={132} label={t("overall")} />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-muted">{isReviewer && s.candidate ? `${s.candidate.full_name || s.candidate.email}, ` : ""}{title}, {fmtDate(s.created_at, lang)}</p>
          <h1 className="mt-1 text-2xl font-semibold text-ink" dir={dir}>{sum.headline || t("overall")}</h1>
          <div className="mt-4 flex flex-wrap gap-6">
            <div><p className="text-sm text-muted">{t("content")}</p><p className="font-display text-xl font-semibold tabular text-ink">{r.content_score ?? "–"}</p></div>
            <div><p className="text-sm text-muted">{t("delivery")}</p><p className="font-display text-xl font-semibold tabular text-ink">{r.delivery_score != null ? Math.round(r.delivery_score) : "–"}</p></div>
            {signal && <div><p className="text-sm text-muted">{t("hiring_signal")}</p>
              <Badge tone={signal === "strong_yes" || signal === "yes" ? "good" : signal === "maybe" ? "warn" : "bad"}>{t(`sig_${signal}` as "sig_yes")}</Badge></div>}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <Button variant="outline" onClick={downloadPdf} busy={pdfBusy}><Download size={16} /> {t("download_pdf")}</Button>
          {!isReviewer && s.mode === "mock" && <Link to="/app/new" className="rounded-xl px-4 py-2.5 text-center text-sm font-medium text-nile hover:bg-nile-soft">{t("practice_again")}</Link>}
        </div>
      </div>

      {isReviewer && s.job_id && <ReviewPanel s={s} />}

      {!!sum.executive_summary?.length && (
        <Panel title={t("summary")}>
          <ul className="list-disc space-y-1.5 ps-5 text-[15px] text-ink" dir={dir}>{sum.executive_summary.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </Panel>
      )}

      {/* human-calibrated */}
      {r.calibrated && r.calibrated.traits.length > 0 && (
        <Panel title={t("calibrated_title")}>
          <p className="mb-5 max-w-3xl text-sm text-muted">{t("calibrated_sub", { h: humanR.toFixed(2) })}</p>
          <ul className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            {r.calibrated.traits.map((x) => (
              <li key={x.trait}>
                <div className="mb-1.5 flex items-baseline justify-between gap-3">
                  <span className="font-medium text-ink">{x.label}</span>
                  <span className="text-sm tabular text-muted">{t("pct", { p: x.percentile })}</span>
                </div>
                <Meter value={x.percentile} />
                <p className="mt-1 text-xs text-muted">{t("reliability")}: r = {x.model_r.toFixed(2)}</p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {/* voice */}
      {v && !v.error && (
        <Panel title={t("voice_title")}>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div><p className="text-sm text-muted">{t("speaking_rate")}</p><p className="font-display text-xl font-semibold tabular text-ink">{v.speaking_rate}</p><p className="text-xs text-muted">{t("wps")}</p></div>
            <div><p className="text-sm text-muted">{t("fillers")}</p><p className="font-display text-xl font-semibold tabular text-ink">{(v.filler_ratio * 100).toFixed(1)}%</p>
              <p className="ltr text-xs text-muted" dir="ltr">{Object.entries(v.filler_words || {}).slice(0, 3).map(([k, n]) => `${k} ×${n}`).join(", ")}</p></div>
            <div><p className="text-sm text-muted">{t("fluency")}</p><p className="font-display text-xl font-semibold text-ink">{level(v.interpretation?.fluency_level)}</p></div>
            <div><p className="text-sm text-muted">{t("confidence")}</p><p className="font-display text-xl font-semibold text-ink">{level(v.interpretation?.confidence_level)}</p></div>
          </div>
        </Panel>
      )}

      {/* per question */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-ink">{t("per_question")}</h2>
        <div className="space-y-3">{(s.answers || []).map((a, i) => <QuestionCard key={a.id} a={a} sid={s.id} open={i === 0} lang={s.language} />)}</div>
      </div>

      {(!!sum.strengths?.length || !!sum.weaknesses?.length) && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel title={t("strengths")}>
            <ul className="space-y-4" dir={dir}>{sum.strengths?.map((x, i) => (
              <li key={i}><p className="font-medium text-ink">{x.competency}</p><p className="text-[15px] text-ink">{x.explanation}</p>
                <p className="mt-1 text-sm text-muted">{t("evidence")}: <span className="ltr" dir="ltr">{x.evidence}</span></p></li>))}</ul>
          </Panel>
          <Panel title={t("weaknesses")}>
            <ul className="space-y-4" dir={dir}>{sum.weaknesses?.map((x, i) => (
              <li key={i}><p className="font-medium text-ink">{x.area}</p><p className="text-[15px] text-ink">{x.feedback}</p></li>))}</ul>
          </Panel>
        </div>
      )}

      {!!sum.learning_plan?.length && !isReviewer && (
        <Panel title={t("learning_plan")}>
          <ol className="space-y-4" dir={dir}>{sum.learning_plan.map((x, i) => (
            <li key={i} className="flex gap-4">
              <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-nile-soft font-display text-sm font-semibold text-nile-deep">{i + 1}</span>
              <div><p className="font-medium text-ink">{x.topic}</p><p className="text-[15px] text-muted">{x.why}</p><p className="mt-1 text-[15px] text-ink">{x.how}</p></div>
            </li>))}</ol>
        </Panel>
      )}

      {(!!sum.next_steps?.length || !!sum.role_fit?.length) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {!!sum.role_fit?.length && <Panel title={t("role_fit")}><ul className="list-disc space-y-1.5 ps-5 text-[15px] text-ink" dir={dir}>{sum.role_fit.map((x, i) => <li key={i}>{x}</li>)}</ul></Panel>}
          {!!sum.next_steps?.length && <Panel title={t("next_steps")}><ul className="list-disc space-y-1.5 ps-5 text-[15px] text-ink" dir={dir}>{sum.next_steps.map((x, i) => <li key={i}>{x}</li>)}</ul></Panel>}
        </div>
      )}
    </div>
  );
}
