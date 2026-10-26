import { useCallback, useEffect, useRef, useState } from "react";

/* ---------------------------------------------------------------------------------------
 * Microphone recorder with live level meter (for the waveform)
 * ------------------------------------------------------------------------------------- */
export type Recording = { blob: Blob; seconds: number; ext: string };

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

  const cleanup = useCallback(() => {
    cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    ctx.current?.close().catch(() => undefined);
    ctx.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    stream.current = s;
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find((m) => window.MediaRecorder?.isTypeSupported(m)) || "";
    const r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
    const chunks: Blob[] = [];
    r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    r.onstop = () => {
      const type = r.mimeType || "audio/webm";
      const ext = type.includes("mp4") ? ".m4a" : type.includes("ogg") ? ".ogg" : ".webm";
      const secs = (Date.now() - started.current) / 1000;
      cleanup();
      setState("idle");
      setLevels(Array(bars).fill(0.08));
      resolver.current?.({ blob: new Blob(chunks, { type }), seconds: secs, ext });
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
      const rms = Math.sqrt(sum / buf.length);
      if (ts - last > 70) {
        hist.shift();
        hist.push(Math.min(1, 0.08 + rms * 4));
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

  return { state, levels, seconds, start, stop };
}

/* ---------------------------------------------------------------------------------------
 * Optional camera presence metrics, computed on-device with MediaPipe Face Landmarker.
 * Only aggregate numbers leave the browser.
 * ------------------------------------------------------------------------------------- */
type Sample = { face: boolean; looking: boolean; smile: number; move: number };

export function usePresence() {
  const [enabled, setEnabled] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const landmarker = useRef<any>(null);
  const samples = useRef<Sample[]>([]);
  const collecting = useRef(false);
  const timer = useRef<number>(0);
  const prevNose = useRef<[number, number] | null>(null);

  const stopCamera = useCallback(() => {
    window.clearInterval(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setReady(false);
  }, []);

  useEffect(() => stopCamera, [stopCamera]);

  const enable = useCallback(async (el: HTMLVideoElement | null) => {
    setError(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" } });
      stream.current = s;
      video.current = el;
      if (el) {
        el.srcObject = s;
        await el.play().catch(() => undefined);
      }
      setEnabled(true);
      if (!landmarker.current) {
        const vision = await import("@mediapipe/tasks-vision");
        const fileset = await vision.FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm");
        landmarker.current = await vision.FaceLandmarker.createFromOptions(fileset, {
          baseOptions: {
            modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          numFaces: 1,
          outputFaceBlendshapes: true,
        });
      }
      timer.current = window.setInterval(() => {
        const v = video.current;
        if (!collecting.current || !v || v.readyState < 2 || !landmarker.current) return;
        const res = landmarker.current.detectForVideo(v, performance.now());
        const lm = res.faceLandmarks?.[0];
        if (!lm) {
          samples.current.push({ face: false, looking: false, smile: 0, move: 0 });
          return;
        }
        const bs: Record<string, number> = {};
        for (const c of res.faceBlendshapes?.[0]?.categories ?? []) bs[c.categoryName] = c.score;
        // head yaw proxy: nose tip relative to the outer eye corners
        const nose = lm[1], l = lm[33], r = lm[263];
        const mid = (l.x + r.x) / 2;
        const yaw = Math.abs(nose.x - mid) / Math.max(1e-3, Math.abs(r.x - l.x));
        const gazeAway = Math.max(bs.eyeLookOutLeft ?? 0, bs.eyeLookOutRight ?? 0, bs.eyeLookInLeft ?? 0, bs.eyeLookInRight ?? 0,
          bs.eyeLookUpLeft ?? 0, bs.eyeLookDownLeft ?? 0);
        const looking = yaw < 0.12 && gazeAway < 0.55;
        const smile = ((bs.mouthSmileLeft ?? 0) + (bs.mouthSmileRight ?? 0)) / 2;
        const p: [number, number] = [nose.x, nose.y];
        const move = prevNose.current ? Math.hypot(p[0] - prevNose.current[0], p[1] - prevNose.current[1]) : 0;
        prevNose.current = p;
        samples.current.push({ face: true, looking, smile, move });
      }, 250);
      setReady(true);
    } catch {
      setError("camera");
      stopCamera();
      setEnabled(false);
    }
  }, [stopCamera]);

  const disable = useCallback(() => {
    stopCamera();
    setEnabled(false);
  }, [stopCamera]);

  const begin = useCallback(() => {
    samples.current = [];
    prevNose.current = null;
    collecting.current = true;
  }, []);

  const end = useCallback((): Record<string, number> | null => {
    collecting.current = false;
    const s = samples.current;
    if (!enabled || s.length < 4) return null;
    const faces = s.filter((x) => x.face);
    const n = Math.max(1, faces.length);
    return {
      face_visible: faces.length / s.length,
      eye_contact: faces.filter((x) => x.looking).length / n,
      smile: faces.reduce((a, x) => a + x.smile, 0) / n,
      head_movement: faces.reduce((a, x) => a + x.move, 0) / n,
      samples: s.length,
    };
  }, [enabled]);

  return { enabled, ready, error, enable, disable, begin, end };
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
