import { getAccessToken } from "./auth";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  const token = await getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined && !form) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  const type = res.headers.get("content-type") || "";
  return (type.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, body?: unknown) => request<T>("POST", p, body ?? {}),
  put: <T>(p: string, body?: unknown) => request<T>("PUT", p, body ?? {}),
  patch: <T>(p: string, body?: unknown) => request<T>("PATCH", p, body ?? {}),
  del: <T>(p: string) => request<T>("DELETE", p),
  upload: <T>(p: string, form: FormData) => request<T>("POST", p, undefined, form),
  blob: (p: string) => request<Blob>("GET", p),
};

/* ---------- shared types ---------- */
export type Profile = {
  id: string;
  email: string | null;
  full_name: string | null;
  role: "candidate" | "recruiter";
  company_id: string | null;
  headline: string | null;
  target_track: string | null;
  locale: string;
  company?: { id: string; name: string; website?: string | null } | null;
};

export type Track = { id: string; en: string; ar: string; group: string };
export type Catalog = { tracks: Track[]; levels: string[]; types: string[] };

export type PlanQuestion = { text: string; kind?: string; skill?: string; rubric?: string; is_followup?: boolean };

export type Feedback = {
  score: number | null;
  relevance?: string | null;
  summary?: string;
  strengths?: string[];
  improvements?: string[];
  delivery_tip?: string;
  improved_answer?: string;
  followup_question?: string;
  skill?: string;
  error?: string;
};

export type Answer = {
  id: string;
  idx: number;
  question: string;
  kind: string | null;
  is_followup: boolean;
  duration_s: number | null;
  transcript: string | null;
  voice: Record<string, any> | null;
  presence: Record<string, number> | null;
  feedback: Feedback | null;
  score: number | null;
  has_audio: boolean;
};

export type Trait = { trait: string; label: string; score_1_7: number; percentile: number; model_r: number; human_r: number };

export type Report = {
  overall: number | null;
  content_score: number | null;
  delivery_score: number | null;
  duration_s?: number;
  voice: Record<string, any>;
  calibrated: { traits: Trait[]; reference: { interviews: number; raters_per_interview: number } } | null;
  summary: {
    headline?: string;
    executive_summary?: string[];
    strengths?: { competency: string; explanation: string; evidence: string }[];
    weaknesses?: { area: string; feedback: string }[];
    role_fit?: string[];
    recommendations?: { category: string; recommendation: string; how_to: string }[];
    learning_plan?: { topic: string; why: string; how: string }[];
    next_steps?: string[];
    hiring_signal?: "strong_yes" | "yes" | "maybe" | "no";
  };
};

export type Session = {
  id: string;
  user_id: string;
  job_id: string | null;
  mode: "mock" | "job" | "upload";
  track: string | null;
  level: string | null;
  interview_type: string | null;
  language: "en" | "ar";
  status: "in_progress" | "processing" | "completed" | "failed";
  context: { plan: PlanQuestion[]; role?: string; answer_seconds?: number; job_title?: string };
  overall_score: number | null;
  report: Report | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  answers?: Answer[];
  job?: { title: string; company: string } | null;
  candidate?: { full_name: string | null; email: string | null; headline: string | null };
};

export type SessionRow = {
  id: string;
  mode: string;
  track: string | null;
  level: string | null;
  status: Session["status"];
  overall_score: number | null;
  created_at: string;
  role: string | null;
  job_title: string | null;
  answered: number;
  planned: number;
};

export type Job = {
  id: string;
  title: string;
  track: string;
  level: string;
  description: string | null;
  questions: PlanQuestion[];
  answer_seconds: number;
  status: "draft" | "open" | "closed";
  share_token: string;
  created_at: string;
  applicants?: number;
  completed?: number;
};

export type CandidateRow = {
  id: string;
  status: Session["status"];
  overall_score: number | null;
  created_at: string;
  content_score: string | null;
  delivery_score: string | null;
  hiring_signal: string | null;
  headline: string | null;
  full_name: string | null;
  email: string | null;
  review_status: "new" | "shortlisted" | "rejected" | "hired";
  rating: number | null;
  notes: string | null;
};
