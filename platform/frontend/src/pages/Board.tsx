import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { JobCard } from "../components/jobs";
import { PublicHeader } from "../components/Shell";
import { Input, Select, Spinner, useCatalog } from "../components/ui";
import { api, type Application, type PublicJob } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

const LEVELS = ["intern", "junior", "mid", "senior", "lead"];

/** The public job board. Rendered inside the app shell for signed-in candidates, and as a public page otherwise. */
export default function Board({ inApp = false }: { inApp?: boolean }) {
  const { t, lang } = useI18n();
  const { profile } = useAuth();
  const catalog = useCatalog();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") || "");
  const [jobs, setJobs] = useState<PublicJob[] | null>(null);
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const f = { track: params.get("track") || "", level: params.get("level") || "", work_mode: params.get("mode") || "", employment_type: params.get("type") || "" };

  const setF = (k: string, v: string) => {
    const n = new URLSearchParams(params);
    if (v) n.set(k, v); else n.delete(k);
    setParams(n, { replace: true });
  };

  useEffect(() => {
    const h = setTimeout(() => {
      const qs = new URLSearchParams({ search: params.get("q") || "", ...f });
      api.get<PublicJob[]>(`/board?${qs}`).then(setJobs).catch(() => setJobs([]));
    }, 200);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  useEffect(() => {
    if (profile?.role === "candidate") api.get<Application[]>("/applications").then((a) => setApplied(new Set(a.map((x) => x.share_token)))).catch(() => undefined);
  }, [profile]);

  useEffect(() => {
    const h = setTimeout(() => setF("q", search.trim()), 350);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const trackOpts = useMemo(() => [{ value: "", label: t("any_track") }, ...(catalog?.tracks ?? []).map((x) => ({ value: x.id, label: lang === "ar" ? x.ar : x.en }))], [catalog, lang, t]);

  const body = (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-ink">{t("board_title")}</h1>
        <p className="mt-1 max-w-2xl text-muted">{t("board_sub")}</p>
      </div>
      <div className="space-y-3 rounded-2xl border border-line bg-surface p-4">
        <label className="relative block">
          <Search size={18} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-muted" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("board_search")} className="ps-10" aria-label={t("board_search")} />
        </label>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Select value={f.track} onChange={(v) => setF("track", v)} options={trackOpts} />
          <Select value={f.level} onChange={(v) => setF("level", v)} options={[{ value: "", label: t("any_level") }, ...LEVELS.map((l) => ({ value: l, label: t(`lv_${l}` as "lv_junior") }))]} />
          <Select value={f.work_mode} onChange={(v) => setF("mode", v)} options={[{ value: "", label: t("any_mode") }, ...["onsite", "remote", "hybrid"].map((m) => ({ value: m, label: t(`wm_${m}` as "wm_onsite") }))]} />
          <Select value={f.employment_type} onChange={(v) => setF("type", v)} options={[{ value: "", label: t("any_type") }, ...["full_time", "part_time", "internship", "contract"].map((m) => ({ value: m, label: t(`et_${m}` as "et_full_time") }))]} />
        </div>
      </div>
      {!jobs ? <Spinner /> : jobs.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line p-8 text-center">
          <p className="text-muted">{t("empty_board")}</p>
          {profile?.role !== "recruiter" && <Link to={profile ? "/app/new" : "/signup"} className="mt-4 inline-block font-medium text-nile hover:underline">{t("cta_candidate")}</Link>}
        </div>
      ) : (
        <ul className="space-y-3">{jobs.map((j) => <JobCard key={j.id} job={j} applied={applied.has(j.share_token)} />)}</ul>
      )}
    </div>
  );

  if (inApp) return body;
  return (
    <div className="min-h-screen">
      <PublicHeader />
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-4 sm:px-6">{body}</main>
    </div>
  );
}
