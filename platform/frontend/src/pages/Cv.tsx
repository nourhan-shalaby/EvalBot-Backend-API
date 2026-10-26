import { FileUp, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CvView } from "../components/insights";
import { Button, ErrorNote, Panel, Spinner, Waveform, fmtDate } from "../components/ui";
import { api, type CvProfile } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function CvPage() {
  const { t, lang } = useI18n();
  const { refresh } = useAuth();
  const input = useRef<HTMLInputElement | null>(null);
  const [cv, setCv] = useState<CvProfile | null | undefined>(undefined);
  const [updated, setUpdated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ cv: CvProfile | null; updated_at: string | null }>("/cv").then((r) => { setCv(r.cv); setUpdated(r.updated_at); }).catch(() => setCv(null));
  }, []);

  const upload = async (f: File) => {
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", f, f.name);
      const r = await api.upload<{ cv: CvProfile }>("/cv", form);
      setCv(r.cv);
      setUpdated(new Date().toISOString());
      await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const remove = async () => {
    await api.del("/cv");
    setCv(null);
    await refresh();
  };

  if (cv === undefined) return <Spinner />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-ink">{t("cv_title")}</h1>
          <p className="mt-1 max-w-2xl text-muted">{t("cv_sub")}</p>
        </div>
        <div className="flex gap-2">
          <input ref={input} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          <Button onClick={() => input.current?.click()} busy={busy}><FileUp size={16} /> {cv ? t("cv_replace") : t("cv_upload")}</Button>
          {cv && <Button variant="quiet" onClick={remove} className="text-danger hover:bg-danger-soft"><Trash2 size={16} /> {t("cv_delete")}</Button>}
        </div>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      {busy ? (
        <Panel><div className="flex flex-col items-center gap-4 py-10"><div className="h-12 w-48"><Waveform animated bars={22} color="var(--color-nile)" /></div><p className="text-muted">{t("cv_reading")}</p></div></Panel>
      ) : cv ? (
        <Panel>
          {updated && <p className="mb-4 text-sm text-muted">{t("cv_updated", { d: fmtDate(updated, lang) })}</p>}
          <CvView cv={cv} />
        </Panel>
      ) : (
        <button onClick={() => input.current?.click()} className="flex w-full flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-line p-12 text-muted hover:border-nile hover:text-nile">
          <FileUp size={32} /> <span className="text-[15px]">{t("cv_upload")}</span>
        </button>
      )}
    </div>
  );
}
