import { ArrowDown, ArrowUp, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, ErrorNote, Field, Input, Panel, Select, Spinner, Textarea, useCatalog } from "../components/ui";
import { api, type Job, type PlanQuestion } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function JobEditor() {
  const { id } = useParams();
  const { t, lang } = useI18n();
  const catalog = useCatalog();
  const nav = useNavigate();
  const [loaded, setLoaded] = useState(!id);
  const [title, setTitle] = useState("");
  const [track, setTrack] = useState("data_engineering");
  const [level, setLevel] = useState("junior");
  const [desc, setDesc] = useState("");
  const [secs, setSecs] = useState(120);
  const [status, setStatus] = useState<Job["status"]>("open");
  const [qs, setQs] = useState<PlanQuestion[]>([{ text: "" }]);
  const [busy, setBusy] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.get<Job>(`/jobs/${id}`).then((j) => {
      setTitle(j.title); setTrack(j.track); setLevel(j.level); setDesc(j.description || "");
      setSecs(j.answer_seconds); setStatus(j.status); setQs(j.questions.length ? j.questions : [{ text: "" }]);
      setLoaded(true);
    });
  }, [id]);

  const suggest = async () => {
    setSuggesting(true);
    setError(null);
    try {
      const r = await api.post<{ questions: PlanQuestion[] }>("/questions/generate", { track, level, interview_type: "mixed", count: 6, custom_role: title, jd_text: desc });
      setQs((cur) => [...cur.filter((x) => x.text.trim()), ...r.questions]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSuggesting(false);
    }
  };

  const move = (i: number, d: number) => setQs((cur) => {
    const n = [...cur];
    const j = i + d;
    if (j < 0 || j >= n.length) return n;
    [n[i], n[j]] = [n[j], n[i]];
    return n;
  });

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = { title, track, level, description: desc, answer_seconds: secs, status, questions: qs.filter((x) => x.text.trim()) };
      const j = id ? await api.put<Job>(`/jobs/${id}`, body) : await api.post<Job>("/jobs", body);
      nav(`/app/jobs/${j.id}`);
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };

  if (!loaded || !catalog) return <Spinner />;
  const levels = ["intern", "junior", "mid", "senior", "lead"];
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">{id ? title : t("new_job")}</h1>
      <Panel>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("job_title")}><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Junior Data Engineer" /></Field>
          <Field label={t("track")}><Select value={track} onChange={setTrack} options={catalog.tracks.map((x) => ({ value: x.id, label: lang === "ar" ? x.ar : x.en }))} /></Field>
          <Field label={t("level")}><Select value={level} onChange={setLevel} options={levels.map((l) => ({ value: l, label: t(`lv_${l}` as "lv_junior") }))} /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label={t("answer_time")}>
              <Select value={String(secs)} onChange={(v) => setSecs(+v)} options={[60, 90, 120, 180, 240, 300].map((s) => ({ value: String(s), label: `${s / 60} ${t("min")}` }))} />
            </Field>
            <Field label={t("job_status")}>
              <Select value={status} onChange={(v) => setStatus(v as Job["status"])} options={(["open", "draft", "closed"] as const).map((s) => ({ value: s, label: t(`jst_${s}`) }))} />
            </Field>
          </div>
          <div className="md:col-span-2"><Field label={t("job_desc")}><Textarea value={desc} onChange={(e) => setDesc(e.target.value)} /></Field></div>
        </div>
      </Panel>

      <Panel title={t("questions")} action={<Button variant="outline" onClick={suggest} busy={suggesting}><Sparkles size={16} /> {suggesting ? t("suggesting") : t("suggest")}</Button>}>
        <ol className="space-y-3">
          {qs.map((q, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="mt-2.5 w-6 flex-none text-center text-sm tabular text-muted">{i + 1}</span>
              <Textarea value={q.text} onChange={(e) => setQs((cur) => cur.map((x, k) => (k === i ? { ...x, text: e.target.value } : x)))}
                placeholder={t("question_ph")} className="ltr min-h-16" dir="ltr" />
              <div className="flex flex-col">
                <button onClick={() => move(i, -1)} className="rounded p-1 text-muted hover:bg-sunken" aria-label="Move up"><ArrowUp size={16} /></button>
                <button onClick={() => move(i, 1)} className="rounded p-1 text-muted hover:bg-sunken" aria-label="Move down"><ArrowDown size={16} /></button>
              </div>
              <button onClick={() => setQs((cur) => cur.filter((_, k) => k !== i))} className="mt-1 rounded-lg p-2 text-muted hover:bg-danger-soft hover:text-danger" aria-label={t("delete")}>
                <Trash2 size={16} />
              </button>
            </li>
          ))}
        </ol>
        <Button variant="quiet" className="mt-3" onClick={() => setQs((cur) => [...cur, { text: "" }])}><Plus size={16} /> {t("add_question")}</Button>
      </Panel>

      {error && <ErrorNote>{error}</ErrorNote>}
      <div className="flex justify-end gap-3">
        <Button variant="quiet" onClick={() => nav(-1)}>{t("cancel")}</Button>
        <Button size="lg" onClick={save} busy={busy} disabled={title.trim().length < 2 || !qs.some((x) => x.text.trim())}>{t("save_job")}</Button>
      </div>
    </div>
  );
}
