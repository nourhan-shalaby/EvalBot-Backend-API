import { Camera, CameraOff, Eye, EyeOff, Mic, ShieldCheck, Square, Users, Video, Volume2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button, ErrorNote, Logo, Spinner, Waveform } from "../components/ui";
import { api, type Session } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { fmtClock, speak, stopSpeaking, useRecorder, type Recording } from "../lib/media";
import { useVision } from "../lib/vision";

type Next = { done: boolean; idx?: number; total: number; question?: string; kind?: string; is_followup?: boolean; answer_seconds?: number };
type Phase = "loading" | "asking" | "ready" | "recording" | "review_short" | "saving" | "waiting_followup" | "done" | "finishing";

export default function InterviewRoom() {
  const { id } = useParams();
  const { t } = useI18n();
  const nav = useNavigate();
  const rec = useRecorder(36);
  const presence = useVision(rec.level);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [next, setNext] = useState<Next | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(0);
  const pending = useRef<Recording | null>(null);
  const autoStop = useRef<number>(0);

  const needsCamera = !!(session?.context as any)?.require_camera || !!(session?.context as any)?.record_video;
  const recordVideo = !!(session?.context as any)?.record_video;
  const proctored = session?.mode === "job" && !!(session?.context as any)?.require_camera;

  const ask = useCallback((n: Next) => {
    setNext(n);
    if (n.done || !n.question) return;
    setPhase("asking");
    speak(n.question, () => setPhase((p) => (p === "asking" ? "ready" : p)));
  }, []);

  const loadNext = useCallback(async () => {
    const n = await api.get<Next>(`/sessions/${id}/next`);
    if (n.done) {
      setNext(n);
      setPhase("waiting_followup");
      // give the last answer's analysis a moment to propose a follow-up question
      for (let i = 0; i < 8; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const m = await api.get<Next>(`/sessions/${id}/next`);
        if (!m.done) {
          ask(m);
          return;
        }
      }
      setPhase("done");
    } else ask(n);
  }, [id, ask]);

  useEffect(() => {
    api.get<Session>(`/sessions/${id}`).then((s) => {
      setSession(s);
      if (s.status !== "in_progress") {
        nav(`/app/report/${id}`, { replace: true });
        return;
      }
      setSaved(s.answers?.length ?? 0);
      loadNext().catch((e) => setError(e.message));
    }).catch((e) => setError(e.message));
    return () => stopSpeaking();
  }, [id, nav, loadNext]);

  const upload = useCallback(async (r: Recording) => {
    if (!next || next.idx == null) return;
    setPhase("saving");
    const form = new FormData();
    form.append("idx", String(next.idx));
    form.append("file", r.blob, `answer${r.ext}`);
    const p = presence.end();
    if (p.samples > 0 || p.events.length) form.append("presence", JSON.stringify(p));
    try {
      await api.upload(`/sessions/${id}/answers`, form);
      setSaved((x) => x + 1);
      await loadNext();
    } catch (e: any) {
      setError(e.message);
      setPhase("ready");
    }
  }, [next, id, presence, loadNext]);

  const startAnswer = async () => {
    stopSpeaking();
    setError(null);
    if (needsCamera && !presence.ready) {
      setError(t("cam_required_body"));
      return;
    }
    if (proctored && !document.fullscreenElement) await document.documentElement.requestFullscreen?.().catch(() => undefined);
    try {
      await rec.start({ video: recordVideo && presence.enabled ? presence.stream.current : null });
      presence.begin({ fullscreen: proctored && !!document.fullscreenElement });
      setPhase("recording");
      const limit = (next?.answer_seconds ?? session?.context.answer_seconds ?? 120) * 1000;
      window.clearTimeout(autoStop.current);
      autoStop.current = window.setTimeout(() => stopAnswer(), limit);
    } catch {
      setError(t("mic_error"));
    }
  };

  const stopAnswer = async () => {
    window.clearTimeout(autoStop.current);
    const r = await rec.stop();
    if (r.seconds < 3) {
      pending.current = r;
      setPhase("review_short");
      return;
    }
    upload(r);
  };

  const finish = async () => {
    setPhase("finishing");
    stopSpeaking();
    presence.disable();
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => undefined);
    try {
      await api.post(`/sessions/${id}/finish`);
      nav(`/app/report/${id}`, { replace: true });
    } catch (e: any) {
      setError(e.message);
      setPhase("done");
    }
  };

  if (!session && !error) return <Spinner />;
  const isJob = session?.mode === "job";
  const live = presence.live;
  const limit = next?.answer_seconds ?? session?.context.answer_seconds ?? 120;
  const total = next?.total ?? session?.context.plan.length ?? 0;
  const qNumber = (next?.idx ?? 0) + 1;

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="flex items-center justify-between gap-4 border-b border-line bg-surface px-4 py-3 sm:px-6">
        <Link to="/app" aria-label="Dashboard"><Logo size={24} /></Link>
        <div className="flex flex-1 items-center justify-center gap-3">
          {total > 0 && (
            <div className="hidden w-64 items-center gap-3 sm:flex" aria-label={t("q_of", { n: Math.min(qNumber, total), total })}>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
                <div className="h-full rounded-full bg-nile transition-all" style={{ width: `${(saved / total) * 100}%` }} />
              </div>
              <span className="text-sm tabular text-muted">{saved}/{total}</span>
            </div>
          )}
        </div>
        <Button variant="outline" onClick={finish} disabled={saved === 0 || phase === "recording" || phase === "finishing"}>{t("finish_now")}</Button>
      </header>

      <main className="mx-auto grid w-full max-w-5xl flex-1 gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_260px]">
        <section className="flex flex-col">
          {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}

          {phase === "finishing" || phase === "done" || phase === "waiting_followup" ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
              <div className="h-16 w-60"><Waveform animated={phase !== "done"} bars={28} color="var(--color-nile)" /></div>
              <p className="font-display text-2xl text-ink">{t("interview_done")}</p>
              <p className="text-muted">{t("answers_saved", { n: saved })}</p>
              <Button size="lg" onClick={finish} busy={phase === "finishing"} disabled={phase === "waiting_followup"}>{t("finish_now")}</Button>
            </div>
          ) : (
            <>
              {/* interviewer */}
              <div className="rounded-3xl border border-line bg-surface p-6 sm:p-8">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-muted">
                    {next?.is_followup ? t("followup") : t("q_of", { n: qNumber, total })}
                  </p>
                  {next?.question && (
                    <button onClick={() => { setPhase("asking"); speak(next.question!, () => setPhase((p) => (p === "asking" ? "ready" : p))); }}
                      disabled={phase === "recording"} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-nile hover:bg-nile-soft disabled:opacity-40">
                      <Volume2 size={16} /> {t("listen_again")}
                    </button>
                  )}
                </div>
                <p className="ltr mt-4 font-display text-2xl font-medium leading-snug text-ink sm:text-[1.7rem]" dir="ltr">
                  {phase === "loading" ? "…" : next?.question}
                </p>
                <div className="mt-6 h-8 w-40">{phase === "asking" && <Waveform animated bars={18} color="var(--color-nile)" />}</div>
              </div>

              {/* candidate */}
              <div className="mt-6 rounded-3xl border border-line bg-surface p-6 sm:p-8">
                {phase === "review_short" ? (
                  <div className="space-y-4 text-center">
                    <p className="text-ink">{t("too_short")}</p>
                    <div className="flex justify-center gap-3">
                      <Button onClick={startAnswer}>{t("record_again")}</Button>
                      <Button variant="outline" onClick={() => pending.current && upload(pending.current)}>{t("use_it")}</Button>
                    </div>
                  </div>
                ) : phase === "saving" ? (
                  <Spinner label={t("uploading")} />
                ) : (
                  <div className="flex flex-col items-center gap-5">
                    <div className="h-16 w-full max-w-md">
                      <Waveform levels={phase === "recording" ? rec.levels : undefined} bars={36}
                        color={phase === "recording" ? "var(--color-amber)" : "var(--color-line)"} />
                    </div>
                    {phase === "recording" ? (
                      <>
                        <p className="flex items-center gap-2 text-sm tabular text-danger">
                          <span className="pulse-dot h-2.5 w-2.5 rounded-full bg-danger" /> {t("recording")} {fmtClock(rec.seconds)}
                          <span className="text-muted">· {t("time_left", { t: fmtClock(limit - rec.seconds) })}</span>
                        </p>
                        <Button size="lg" variant="danger" onClick={stopAnswer}><Square size={18} /> {t("stop_answer")}</Button>
                      </>
                    ) : (
                      <>
                        <p className="text-sm text-muted">{t("get_ready")}</p>
                        <Button size="lg" onClick={startAnswer} disabled={phase === "loading" || (needsCamera && !presence.ready)}>
                          {recordVideo ? <Video size={18} /> : <Mic size={18} />} {t("start_answer")}
                        </Button>
                        {needsCamera && !presence.ready && <p className="max-w-sm text-center text-sm text-muted">{t("cam_required_body")}</p>}
                      </>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </section>

        {/* camera */}
        <aside className="space-y-3">
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-line bg-sunken">
            <video ref={videoRef} muted playsInline className={`h-full w-full scale-x-[-1] object-cover ${presence.enabled ? "" : "hidden"}`} />
            {!presence.enabled && <div className="flex h-full items-center justify-center text-muted"><CameraOff size={28} /></div>}
            {presence.enabled && phase === "recording" && recordVideo && (
              <span className="absolute start-2 top-2 flex items-center gap-1.5 rounded-full bg-danger px-2 py-0.5 text-xs font-medium text-white">
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-white" /> REC
              </span>
            )}
            {presence.ready && (
              <div className="absolute inset-x-2 bottom-2 flex flex-wrap gap-1.5">
                {live.faces > 1 && <span className="flex items-center gap-1 rounded-full bg-danger px-2 py-0.5 text-xs text-white"><Users size={12} /> {t("live_faces")}</span>}
                {live.faces === 0 && <span className="rounded-full bg-amber px-2 py-0.5 text-xs text-ink">{t("live_noface")}</span>}
                {live.faces === 1 && (
                  <span className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${live.looking ? "bg-nile text-white" : "bg-amber text-ink"}`}>
                    {live.looking ? <Eye size={12} /> : <EyeOff size={12} />} {live.looking ? t("live_looking") : t("live_away")}
                  </span>
                )}
                {!isJob && live.emotion && live.faces === 1 && (
                  <span className="rounded-full bg-ink/75 px-2 py-0.5 text-xs text-white">{t(`emo_${live.emotion}` as "emo_happy")} {Math.round(live.confidence * 100)}%</span>
                )}
              </div>
            )}
          </div>
          <Button variant="outline" className="w-full" onClick={() => (presence.enabled ? presence.disable() : presence.enable(videoRef.current))}
            disabled={phase === "recording" || (needsCamera && presence.enabled)}>
            {presence.enabled ? <><CameraOff size={16} /> {t("camera_off")}</> : <><Camera size={16} /> {t("camera_on")}</>}
          </Button>
          {presence.error && <p className="text-xs text-danger">{t("cam_error")}</p>}
          {needsCamera ? (
            <div className="space-y-2 rounded-xl border border-line bg-surface p-3 text-xs text-muted">
              <p className="flex items-center gap-1.5 font-medium text-ink"><ShieldCheck size={14} className="text-nile" /> {t("proctor_title")}</p>
              <p>{t("proctor_body")}</p>
              {recordVideo && <p className="font-medium text-ink">{t("video_notice")}</p>}
            </div>
          ) : (
            <p className="text-xs text-muted">{t("camera_hint")}</p>
          )}
        </aside>
      </main>
    </div>
  );
}
