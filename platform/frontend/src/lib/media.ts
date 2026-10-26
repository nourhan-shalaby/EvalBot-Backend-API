import { useCallback, useEffect, useRef, useState } from "react";

/* ---------------------------------------------------------------------------------------
 * Microphone recorder with live level meter (for the waveform)
 * ------------------------------------------------------------------------------------- */
export type Recording = { blob: Blob; seconds: number; ext: string; video: boolean };

export function useRecorder(bars = 32) {
  const [state, setState] = useState<"idle" | "recording">("idle");
  const [levels, setLevels] = useState<number[]>(Array(bars).fill(0.08));
  const [seconds, setSeconds] = useState(0);
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const raf = useRef<number>(0);
  const started = useRef(0);
  const resolver = useRef<((r: Recording) => void) | null>(null);
  const rms = useRef(0);
  /** Current microphone level (0-1), for lip-sync checks. */
  const level = useCallback(() => rms.current, []);

  const cleanup = useCallback(() => {
    cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    ctx.current?.close().catch(() => undefined);
    ctx.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  /** Start recording. Pass the camera stream to record a video answer (low bitrate, ~2-3 MB per minute). */
  const start = useCallback(async (opts?: { video?: MediaStream | null }) => {
    const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    stream.current = s;
    const videoTracks = opts?.video?.getVideoTracks().filter((t) => t.readyState === "live") ?? [];
    const withVideo = videoTracks.length > 0;
    const recStream = withVideo ? new MediaStream([...videoTracks, ...s.getAudioTracks()]) : s;
    const types = withVideo
      ? ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"]
      : ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
    const mime = types.find((m) => window.MediaRecorder?.isTypeSupported(m)) || "";
    const r = new MediaRecorder(recStream, {
      ...(mime ? { mimeType: mime } : {}),
      ...(withVideo ? { videoBitsPerSecond: 350_000, audioBitsPerSecond: 64_000 } : {}),
    });
    const chunks: Blob[] = [];
    r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    r.onstop = () => {
      const type = r.mimeType || (withVideo ? "video/webm" : "audio/webm");
      const ext = type.includes("mp4") ? (withVideo ? ".mp4" : ".m4a") : type.includes("ogg") ? ".ogg" : ".webm";
      const secs = (Date.now() - started.current) / 1000;
      cleanup();
      rms.current = 0;
      setState("idle");
      setLevels(Array(bars).fill(0.08));
      resolver.current?.({ blob: new Blob(chunks, { type }), seconds: secs, ext, video: withVideo });
    };
    // level meter
    const ac = new AudioContext();
    ctx.current = ac;
    const an = ac.createAnalyser();
    an.fftSize = 512;
    ac.createMediaStreamSource(s).connect(an);
    const buf = new Uint8Array(an.fftSize);
    const hist: number[] = Array(bars).fill(0.08);
    let last = 0;
    const tick = (ts: number) => {
      an.getByteTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) sum += ((v - 128) / 128) ** 2;
      const level = Math.sqrt(sum / buf.length);
      rms.current = level;
      if (ts - last > 70) {
        hist.shift();
        hist.push(Math.min(1, 0.08 + level * 4));
        setLevels([...hist]);
        setSeconds((Date.now() - started.current) / 1000);
        last = ts;
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    started.current = Date.now();
    setSeconds(0);
    r.start(1000);
    rec.current = r;
    setState("recording");
  }, [bars, cleanup]);

  const stop = useCallback(
    () =>
      new Promise<Recording>((resolve) => {
        resolver.current = resolve;
        if (rec.current && rec.current.state !== "inactive") rec.current.stop();
      }),
    [],
  );

  return { state, levels, seconds, start, stop, level };
}

/* ---------------------------------------------------------------------------------------
 * Interviewer voice: the browser's speech synthesis
 * ------------------------------------------------------------------------------------- */
export function speak(text: string, onEnd?: () => void) {
  if (!("speechSynthesis" in window)) {
    onEnd?.();
    return;
  }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.rate = 0.97;
  const voices = speechSynthesis.getVoices();
  const v = voices.find((x) => /en-(US|GB)/.test(x.lang) && /Google|Natural|Samantha|Daniel/.test(x.name)) || voices.find((x) => x.lang?.startsWith("en"));
  if (v) u.voice = v;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  speechSynthesis.speak(u);
}

export function stopSpeaking() {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

export function fmtClock(s: number) {
  const v = Math.max(0, Math.round(s));
  return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, "0")}`;
}
