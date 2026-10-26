/* ---------------------------------------------------------------------------------------
 * On-device camera analysis for interviews.
 *
 * - Face landmarks, iris position, head pose and blendshapes: MediaPipe Face Landmarker
 * - Facial expressions (7 classes, FER2013-style): face-api expression network on the face crop,
 *   smoothed with an exponential moving average (alpha 0.3)
 * - Integrity flags for human review: looking away, face missing, more than one face,
 *   voice while the lips are still, reading-like eye movement, leaving the tab, leaving full screen
 *
 * Only numbers leave the browser. The video itself is sent only when a company asks for a
 * video interview, and then as the answer recording.
 * ------------------------------------------------------------------------------------- */
import { useCallback, useEffect, useRef, useState } from "react";

export const EMOTIONS = ["neutral", "happy", "surprised", "sad", "angry", "fearful", "disgusted"] as const;
export type Emotion = (typeof EMOTIONS)[number];
export type Probs = Record<Emotion, number>;
export type IntegrityEvent = { type: string; t: number; dur?: number };
export type CameraMetrics = {
  samples: number; face_visible?: number; eye_contact?: number; smile?: number; head_movement?: number;
  emotions?: Probs; timeline?: { t: number; dominant: Emotion; probs: Probs }[]; events: IntegrityEvent[];
};
export type Live = { faces: number; looking: boolean; emotion: Emotion | null; confidence: number };

const zero = (): Probs => ({ neutral: 0, happy: 0, surprised: 0, sad: 0, angry: 0, fearful: 0, disgusted: 0 });
const SAMPLE_MS = 200;
const SEGMENT_S = 5;

type Sample = { t: number; face: boolean; looking: boolean; smile: number; move: number; probs: Probs | null };

/** A condition that must hold for `minS` seconds before it becomes an event. */
class Sustained {
  private since: number | null = null;
  constructor(private type: string, private minS: number, private emit: (e: IntegrityEvent) => void) {}
  update(active: boolean, t: number) {
    if (active && this.since == null) this.since = t;
    if (!active && this.since != null) this.close(t);
  }
  close(t: number) {
    if (this.since != null && t - this.since >= this.minS) this.emit({ type: this.type, t: round1(this.since), dur: round1(t - this.since) });
    this.since = null;
  }
}
const round1 = (v: number) => Math.round(v * 10) / 10;

export function useVision(micLevel: () => number) {
  const [enabled, setEnabled] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<Live>({ faces: 0, looking: true, emotion: null, confidence: 0 });
  const video = useRef<HTMLVideoElement | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const landmarker = useRef<any>(null);
  const fer = useRef<any>(null);
  const crop = useRef<HTMLCanvasElement | null>(null);
  const timer = useRef<number>(0);
  const busy = useRef(false);
  const tick = useRef(0);

  // per-answer state
  const collecting = useRef(false);
  const t0 = useRef(0);
  const samples = useRef<Sample[]>([]);
  const events = useRef<IntegrityEvent[]>([]);
  const ema = useRef<Probs | null>(null);
  const prevNose = useRef<[number, number] | null>(null);
  const lipHist = useRef<{ t: number; v: number }[]>([]);
  const voiceHist = useRef<{ t: number; v: boolean }[]>([]);
  const gazeHist = useRef<{ t: number; x: number }[]>([]);
  const sweeps = useRef<number[]>([]);
  const detectors = useRef<Record<string, Sustained>>({});
  const away = useRef<{ hidden: number | null; fs: boolean }>({ hidden: null, fs: false });

  const now = () => (performance.now() - t0.current) / 1000;
  const emit = useCallback((e: IntegrityEvent) => {
    if (collecting.current) events.current.push(e);
  }, []);

  const stopCamera = useCallback(() => {
    window.clearInterval(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setReady(false);
  }, []);
  useEffect(() => stopCamera, [stopCamera]);

  /* ---------- tab / window / full-screen focus (works with the camera on or off) ---------- */
  useEffect(() => {
    const leave = () => {
      if (collecting.current && away.current.hidden == null) away.current.hidden = now();
    };
    const back = () => {
      const h = away.current.hidden;
      if (collecting.current && h != null) {
        const d = now() - h;
        if (d >= 1) emit({ type: "tab_hidden", t: round1(h), dur: round1(d) });
      }
      away.current.hidden = null;
    };
    const vis = () => (document.hidden ? leave() : back());
    const fs = () => {
      if (collecting.current && away.current.fs && !document.fullscreenElement) emit({ type: "fullscreen_exit", t: round1(now()) });
    };
    document.addEventListener("visibilitychange", vis);
    window.addEventListener("blur", leave);
    window.addEventListener("focus", back);
    document.addEventListener("fullscreenchange", fs);
    return () => {
      document.removeEventListener("visibilitychange", vis);
      window.removeEventListener("blur", leave);
      window.removeEventListener("focus", back);
      document.removeEventListener("fullscreenchange", fs);
    };
  }, [emit]);

  /* ---------- one analysis step ---------- */
  const step = useCallback(async () => {
    const v = video.current;
    if (busy.current || !v || v.readyState < 2 || !landmarker.current) return;
    busy.current = true;
    try {
      const res = landmarker.current.detectForVideo(v, performance.now());
      const faces: any[] = res.faceLandmarks ?? [];
      const t = now();
      const lm = faces[0];
      let looking = false, smile = 0, move = 0, lipOpen = 0;
      let probs: Probs | null = null;
      if (lm) {
        const bs: Record<string, number> = {};
        for (const c of res.faceBlendshapes?.[0]?.categories ?? []) bs[c.categoryName] = c.score;
        smile = ((bs.mouthSmileLeft ?? 0) + (bs.mouthSmileRight ?? 0)) / 2;

        // head pose: yaw / pitch in degrees from the facial transformation matrix
        let yaw = 0, pitch = 0;
        const m = res.facialTransformationMatrixes?.[0]?.data;
        if (m && m.length >= 11) {
          yaw = (Math.asin(Math.max(-1, Math.min(1, -m[2]))) * 180) / Math.PI;
          pitch = (Math.atan2(m[6], m[10]) * 180) / Math.PI;
          if (Math.abs(pitch) > 90) pitch = pitch > 0 ? 180 - pitch : -180 - pitch;
        } else {
          const nose = lm[1], l = lm[33], r = lm[263];
          yaw = ((nose.x - (l.x + r.x) / 2) / Math.max(1e-3, Math.abs(r.x - l.x))) * 90;
        }

        // gaze: iris centre relative to the eye corners (0.5 = centred)
        let gazeX = 0.5, gazeOff = 0;
        if (lm.length > 473) {
          const eyes = [[33, 133, 159, 145], [362, 263, 386, 374]];
          const irises = [lm[468], lm[473]];
          let sumX = 0, sumOff = 0;
          for (const [a, b, top, bot] of eyes) {
            const ca = lm[a], cb = lm[b];
            const mid = { x: (ca.x + cb.x) / 2, y: (ca.y + cb.y) / 2 };
            const iris = irises.reduce((p, q) => (Math.hypot(q.x - mid.x, q.y - mid.y) < Math.hypot(p.x - mid.x, p.y - mid.y) ? q : p));
            const w = Math.max(1e-3, Math.abs(cb.x - ca.x));
            const rx = (iris.x - Math.min(ca.x, cb.x)) / w;
            const h = Math.max(1e-3, Math.abs(lm[bot].y - lm[top].y));
            const ry = (iris.y - lm[top].y) / h;
            sumX += rx;
            sumOff += Math.max(Math.abs(rx - 0.5), Math.abs(ry - 0.5) * 0.6);
          }
          gazeX = sumX / 2;
          gazeOff = sumOff / 2;
        }
        looking = Math.abs(yaw) <= 15 && Math.abs(pitch) <= 15 && gazeOff <= 0.2;

        // lips (inner lip distance relative to face height)
        const faceH = Math.max(1e-3, Math.hypot(lm[152].x - lm[10].x, lm[152].y - lm[10].y));
        lipOpen = Math.hypot(lm[14].x - lm[13].x, lm[14].y - lm[13].y) / faceH;

        const p: [number, number] = [lm[1].x, lm[1].y];
        move = prevNose.current ? Math.hypot(p[0] - prevNose.current[0], p[1] - prevNose.current[1]) : 0;
        prevNose.current = p;

        // facial expression on every other sample
        if (fer.current && tick.current++ % 2 === 0) {
          const xs = lm.map((q: any) => q.x), ys = lm.map((q: any) => q.y);
          const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
          const W = v.videoWidth, H = v.videoHeight, pad = 0.12;
          const sx = Math.max(0, (x0 - (x1 - x0) * pad) * W), sy = Math.max(0, (y0 - (y1 - y0) * pad) * H);
          const sw = Math.min(W - sx, (x1 - x0) * (1 + 2 * pad) * W), sh = Math.min(H - sy, (y1 - y0) * (1 + 2 * pad) * H);
          if (sw > 20 && sh > 20) {
            const c = (crop.current ??= Object.assign(document.createElement("canvas"), { width: 112, height: 112 }));
            c.getContext("2d")!.drawImage(v, sx, sy, sw, sh, 0, 0, 112, 112);
            const out = await fer.current.predictExpressions(c);
            const raw: any = Array.isArray(out) ? out[0] : out;
            if (raw) {
              const cur = zero();
              for (const e of EMOTIONS) cur[e] = Number(raw[e] ?? 0);
              const prev = ema.current;
              ema.current = prev ? (Object.fromEntries(EMOTIONS.map((e) => [e, 0.3 * cur[e] + 0.7 * prev[e]])) as Probs) : cur;
            }
          }
        }
        probs = ema.current;

        // ---- integrity detectors (only while an answer is being recorded) ----
        if (collecting.current) {
          lipHist.current.push({ t, v: lipOpen });
          voiceHist.current.push({ t, v: micLevel() > 0.045 });
          gazeHist.current.push({ t, x: gazeX });
          const keep = (arr: { t: number }[], s: number) => { while (arr.length && arr[0].t < t - s) arr.shift(); };
          keep(lipHist.current, 2); keep(voiceHist.current, 2); keep(gazeHist.current, 3);
          const lipRange = Math.max(...lipHist.current.map((x) => x.v)) - Math.min(...lipHist.current.map((x) => x.v));
          const voiced = voiceHist.current.filter((x) => x.v).length / Math.max(1, voiceHist.current.length);
          detectors.current.voice_without_lips?.update(voiced > 0.6 && lipRange < 0.012 && t > 3, t);
          // reading: slow left-to-right drift followed by a quick jump back, repeated while speaking
          const g = gazeHist.current;
          if (g.length > 3 && voiced > 0.4) {
            const jump = g[g.length - 2].x - g[g.length - 1].x;
            const drift = g[g.length - 2].x - g[0].x;
            if (jump > 0.12 && drift > 0.08) {
              sweeps.current.push(t);
              gazeHist.current = [];
            }
          }
          sweeps.current = sweeps.current.filter((x) => x > t - 20);
          if (sweeps.current.length >= 4) {
            emit({ type: "reading_pattern", t: round1(sweeps.current[0]), dur: round1(t - sweeps.current[0]) });
            sweeps.current = [];
          }
        }
      } else {
        prevNose.current = null;
      }
      if (collecting.current) {
        detectors.current.no_face?.update(!lm, t);
        detectors.current.multiple_faces?.update(faces.length > 1, t);
        detectors.current.looking_away?.update(!!lm && !looking, t);
        samples.current.push({ t, face: !!lm, looking, smile, move, probs });
      }
      const top = probs ? EMOTIONS.reduce((a, b) => (probs![b] > probs![a] ? b : a)) : null;
      setLive({ faces: faces.length, looking, emotion: top, confidence: top && probs ? probs[top] : 0 });
    } catch {
      /* skip a frame */
    } finally {
      busy.current = false;
    }
  }, [emit, micLevel]);

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
          numFaces: 2,
          outputFaceBlendshapes: true,
          outputFacialTransformationMatrixes: true,
        });
      }
      if (!fer.current) {
        try {
          const faceapi = await import("@vladmandic/face-api");
          const tf: any = (faceapi as any).tf;
          try {
            await tf.setBackend("webgl");
          } catch {
            await tf.setBackend("cpu");
          }
          await tf.ready();
          await faceapi.nets.faceExpressionNet.loadFromUri("/models");
          fer.current = faceapi.nets.faceExpressionNet;
        } catch {
          fer.current = null; // expressions unavailable; the rest still works
        }
      }
      window.clearInterval(timer.current);
      timer.current = window.setInterval(step, SAMPLE_MS);
      setReady(true);
    } catch {
      setError("camera");
      stopCamera();
      setEnabled(false);
    }
  }, [step, stopCamera]);

  const disable = useCallback(() => {
    stopCamera();
    setEnabled(false);
  }, [stopCamera]);

  /** Start measuring one answer. `fullscreen` marks that the interview asked for full screen. */
  const begin = useCallback((opts?: { fullscreen?: boolean }) => {
    t0.current = performance.now();
    samples.current = [];
    events.current = [];
    lipHist.current = [];
    voiceHist.current = [];
    gazeHist.current = [];
    sweeps.current = [];
    prevNose.current = null;
    away.current = { hidden: null, fs: !!opts?.fullscreen };
    detectors.current = {
      looking_away: new Sustained("looking_away", 2.5, emit),
      no_face: new Sustained("no_face", 2, emit),
      multiple_faces: new Sustained("multiple_faces", 1, emit),
      voice_without_lips: new Sustained("voice_without_lips", 3, emit),
    };
    collecting.current = true;
  }, [emit]);

  /** Finish the answer and return its metrics (events are returned even with the camera off). */
  const end = useCallback((): CameraMetrics => {
    const t = now();
    Object.values(detectors.current).forEach((d) => d.close(t));
    if (away.current.hidden != null) {
      const d = t - away.current.hidden;
      if (d >= 1) events.current.push({ type: "tab_hidden", t: round1(away.current.hidden), dur: round1(d) });
      away.current.hidden = null;
    }
    collecting.current = false;
    const s = samples.current;
    const out: CameraMetrics = { samples: enabled ? s.length : 0, events: [...events.current] };
    if (!enabled || s.length < 4) return { ...out, samples: 0 };
    const faces = s.filter((x) => x.face);
    const n = Math.max(1, faces.length);
    out.face_visible = faces.length / s.length;
    out.eye_contact = faces.filter((x) => x.looking).length / n;
    out.smile = faces.reduce((a, x) => a + x.smile, 0) / n;
    out.head_movement = faces.reduce((a, x) => a + x.move, 0) / n;
    const withP = s.filter((x) => x.probs);
    if (withP.length) {
      const avg = zero();
      for (const x of withP) for (const e of EMOTIONS) avg[e] += x.probs![e] / withP.length;
      out.emotions = avg;
      const segs: Record<number, Sample[]> = {};
      for (const x of withP) (segs[Math.floor(x.t / SEGMENT_S)] ??= []).push(x);
      out.timeline = Object.entries(segs).map(([k, arr]) => {
        const p = zero();
        for (const x of arr) for (const e of EMOTIONS) p[e] += x.probs![e] / arr.length;
        const dominant = EMOTIONS.reduce((a, b) => (p[b] > p[a] ? b : a));
        return { t: +k * SEGMENT_S, dominant, probs: p };
      });
    }
    return out;
  }, [enabled]);

  return { enabled, ready, error, live, stream, enable, disable, begin, end };
}
