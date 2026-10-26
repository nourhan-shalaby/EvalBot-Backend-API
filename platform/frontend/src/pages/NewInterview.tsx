import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, ErrorNote, Field, Input, Panel, Spinner, Textarea, Waveform, useCatalog } from "../components/ui";
import { api, type Session } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

const LEVELS = ["intern", "junior", "mid", "senior", "lead"] as const;
const TYPES = ["mixed", "technical", "behavioral", "hr", "case"] as const;

export default function NewInterview() {
  const { t, lang } = useI18n();
  const { profile } = useAuth();
  const catalog = useCatalog();
  const nav = useNavigate();
  const [track, setTrack] = useState(profile?.target_track || "data_engineering");
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState<string>("junior");
  const [itype, setType] = useState<string>("mixed");
  const [count, setCount] = useState(6);
  const [fbLang, setFbLang] = useState<"en" | "ar">(lang);
  const [role, setRole] = useState("");
  const [cv, setCv] = useState("");
  const [jd, setJd] = useState("");
  const [useCv, setUseCv] = useState(!!profile?.has_cv);
  const [recordSelf, setRecordSelf] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (catalog?.tracks ?? []).filter((x) => !q || x.en.toLowerCase().includes(q) || x.ar.includes(q));
    return ["tech", "design", "business", "other"].map((g) => ({ g, items: list.filter((x) => x.group === g) })).filter((x) => x.items.length);
  }, [catalog, query]);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await api.post<Session>("/sessions", { track, level, interview_type: itype, count, custom_role: role, cv_text: useCv ? "" : cv, jd_text: jd, language: fbLang,
        use_cv: useCv, record_video: recordSelf });
      nav(`/app/interview/${s.id}`);
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };

  if (busy)
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-24 text-center">
        <div className="h-16 w-56"><Waveform animated bars={26} color="var(--color-nile)" /></div>
        <p className="text-lg text-ink">{t("preparing")}</p>
      </div>
    );
  if (!catalog) return <Spinner />;

  const chip = (active: boolean) =>
    `rounded-xl border px-3.5 py-2 text-sm text-start transition-colors ${active ? "border-nile bg-nile-soft font-medium text-nile-deep" : "border-line bg-surface text-ink hover:border-nile"}`;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">{t("new_title")}</h1>

      <Panel title={t("track")} action={
        <div className="relative w-48 sm:w-64">
          <Search size={16} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("search_tracks")} className="ps-9" aria-label={t("search_tracks")} />
        </div>
      }>
        <div className="space-y-4">
          {groups.map(({ g, items }) => (
            <div key={g}>
              <p className="mb-2 text-sm text-muted">{t(`g_${g}` as "g_tech")}</p>
              <div className="flex flex-wrap gap-2">
                {items.map((x) => (
                  <button key={x.id} onClick={() => setTrack(x.id)} className={chip(track === x.id)} aria-pressed={track === x.id}>
                    {lang === "ar" ? x.ar : x.en}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title={t("level")}>
          <div className="flex flex-wrap gap-2">
            {LEVELS.map((l) => <button key={l} onClick={() => setLevel(l)} className={chip(level === l)} aria-pressed={level === l}>{t(`lv_${l}` as "lv_junior")}</button>)}
          </div>
          <div className="mt-6 grid grid-cols-2 gap-4">
            <Field label={t("count")}>
              <div className="flex items-center gap-3">
                <input type="range" min={3} max={10} value={count} onChange={(e) => setCount(+e.target.value)} className="flex-1 accent-[var(--color-nile)]" aria-label={t("count")} />
                <span className="w-6 text-center font-display font-semibold tabular text-ink">{count}</span>
              </div>
            </Field>
            <Field label={t("feedback_lang")}>
              <div className="flex gap-2">
                <button onClick={() => setFbLang("en")} className={chip(fbLang === "en")}>{t("english")}</button>
                <button onClick={() => setFbLang("ar")} className={chip(fbLang === "ar")}>{t("arabic")}</button>
              </div>
            </Field>
          </div>
        </Panel>
        <Panel title={t("style")}>
          <div className="grid gap-2">
            {TYPES.map((ty) => (
              <button key={ty} onClick={() => setType(ty)} className={chip(itype === ty)} aria-pressed={itype === ty}>
                <span className="font-medium">{t(`ty_${ty}` as "ty_mixed")}</span>
                <span className="ms-2 text-muted">{t(`ty_${ty}_d` as "ty_mixed_d")}</span>
              </button>
            ))}
          </div>
        </Panel>
      </div>

      <Panel>
        <div className="grid gap-4 lg:grid-cols-3">
          <Field label={`${t("custom_role")} (${t("optional")})`}><Input value={role} onChange={(e) => setRole(e.target.value)} placeholder={t("custom_role_ph")} /></Field>
          <Field label={`${t("jd")} (${t("optional")})`}><Textarea value={jd} onChange={(e) => setJd(e.target.value)} placeholder={t("jd_ph")} /></Field>
          {useCv ? (
            <div>
              <span className="mb-1.5 block text-sm font-medium text-ink">{t("cv")}</span>
              <p className="rounded-xl border border-nile bg-nile-soft px-3.5 py-3 text-[15px] text-nile-deep">{t("use_my_cv")} ✓</p>
              <button type="button" onClick={() => setUseCv(false)} className="mt-1.5 text-sm text-muted hover:text-ink">{t("cv_ph")}</button>
            </div>
          ) : (
            <Field label={`${t("cv")} (${t("optional")})`}><Textarea value={cv} onChange={(e) => setCv(e.target.value)} placeholder={t("cv_ph")} /></Field>
          )}
        </div>
        <div className="mt-4 flex flex-col gap-2 border-t border-line pt-4 sm:flex-row sm:flex-wrap sm:gap-6">
          {profile?.has_cv && !useCv && (
            <label className="flex items-center gap-2 text-[15px] text-ink"><input type="checkbox" checked={useCv} onChange={(e) => setUseCv(e.target.checked)} className="h-4 w-4 accent-[var(--color-nile)]" /> {t("use_my_cv")}</label>
          )}
          {!profile?.has_cv && <Link to="/app/cv" className="text-[15px] text-nile hover:underline">{t("cv_upload")}</Link>}
          <label className="flex items-center gap-2 text-[15px] text-ink">
            <input type="checkbox" checked={recordSelf} onChange={(e) => setRecordSelf(e.target.checked)} className="h-4 w-4 accent-[var(--color-nile)]" />
            {t("record_self")} <span className="text-sm text-muted">({t("privacy_video")})</span>
          </label>
        </div>
      </Panel>

      {error && <ErrorNote>{error}</ErrorNote>}
      <div className="flex justify-end"><Button size="lg" onClick={start}>{t("start")}</Button></div>
    </div>
  );
}
