import { Building2, Mic } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/Shell";
import { Button, ErrorNote, Field, Input } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function Onboarding() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [choice, setChoice] = useState<"candidate" | "recruiter">(params.get("as") === "company" ? "recruiter" : "candidate");
  const [company, setCompany] = useState("");
  const [website, setWebsite] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      if (choice === "recruiter") {
        await api.post("/companies", { name: company, website: website || null });
        await refresh();
        nav("/app/jobs");
      } else {
        await api.patch("/me", { role: "candidate" });
        await refresh();
        nav("/app/new");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const option = (key: "candidate" | "recruiter", Icon: typeof Mic, title: string, desc: string) => (
    <button type="button" onClick={() => setChoice(key)} aria-pressed={choice === key}
      className={`flex w-full items-start gap-4 rounded-2xl border p-5 text-start transition-colors ${choice === key ? "border-nile bg-nile-soft" : "border-line bg-surface hover:border-nile"}`}>
      <Icon className={choice === key ? "text-nile" : "text-muted"} size={24} />
      <span>
        <span className="block font-semibold text-ink">{title}</span>
        <span className="mt-0.5 block text-sm text-muted">{desc}</span>
      </span>
    </button>
  );

  return (
    <div className="min-h-screen">
      <PublicHeader />
      <main className="mx-auto max-w-lg px-4 pb-16 pt-8">
        <h1 className="text-3xl font-semibold text-ink">{t("onboard_title")}</h1>
        <div className="mt-8 space-y-3">
          {option("candidate", Mic, t("onboard_candidate"), t("onboard_candidate_d"))}
          {option("recruiter", Building2, t("onboard_recruiter"), t("onboard_recruiter_d"))}
        </div>
        {choice === "recruiter" && (
          <div className="mt-6 space-y-4">
            <Field label={t("company_name")}><Input value={company} onChange={(e) => setCompany(e.target.value)} required /></Field>
            <Field label={`${t("website")} (${t("optional")})`}><Input value={website} onChange={(e) => setWebsite(e.target.value)} type="url" placeholder="https://" /></Field>
          </div>
        )}
        {error && <div className="mt-4"><ErrorNote>{error}</ErrorNote></div>}
        <Button className="mt-8 w-full" size="lg" busy={busy} disabled={choice === "recruiter" && company.trim().length < 2} onClick={go}>{t("continue")}</Button>
      </main>
    </div>
  );
}
