import { useEffect, useState } from "react";
import { Button, ErrorNote, Field, Input, Panel, Select, Textarea, useCatalog } from "../components/ui";
import { SIZES } from "./Onboarding";
import { api } from "../lib/api";
import { updatePassword, useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function SettingsPage() {
  const { t, lang } = useI18n();
  const { profile, refresh, config } = useAuth();
  const catalog = useCatalog();
  const [name, setName] = useState("");
  const [headline, setHeadline] = useState("");
  const [track, setTrack] = useState("");
  const [company, setCompany] = useState("");
  const [co, setCo] = useState({ website: "", industry: "", size: "11-50", location: "", about: "" });
  const [pw, setPw] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!profile) return;
    setName(profile.full_name || "");
    setHeadline(profile.headline || "");
    setTrack(profile.target_track || "");
    setCompany(profile.company?.name || "");
    const c = profile.company;
    if (c) setCo({ website: c.website || "", industry: c.industry || "", size: c.size || "11-50", location: c.location || "", about: c.about || "" });
  }, [profile]);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.patch("/me", { full_name: name, headline, target_track: track || null });
      if (profile?.role === "recruiter" && company.trim()) await api.post("/companies", { name: company.trim(), ...co });
      await refresh();
      setMsg(t("saved"));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const changePw = async () => {
    try {
      await updatePassword(pw);
      setPw("");
      setMsg(t("password_changed"));
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">{t("settings_title")}</h1>
      <Panel title={t("profile")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("full_name")}><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label={t("email")}><Input value={profile?.email || ""} disabled /></Field>
          <Field label={t("headline")}><Input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder={t("headline_ph")} /></Field>
          <Field label={t("target_track")}>
            <Select value={track} onChange={setTrack} options={[{ value: "", label: "—" }, ...(catalog?.tracks ?? []).map((x) => ({ value: x.id, label: lang === "ar" ? x.ar : x.en }))]} />
          </Field>
        </div>
        {profile?.role === "recruiter" && (
          <div className="mt-6 grid gap-4 border-t border-line pt-6 sm:grid-cols-2">
            <Field label={t("company_name")}><Input value={company} onChange={(e) => setCompany(e.target.value)} /></Field>
            <Field label={t("website")}><Input value={co.website} onChange={(e) => setCo({ ...co, website: e.target.value })} type="url" placeholder="https://" /></Field>
            <Field label={t("industry")}><Input value={co.industry} onChange={(e) => setCo({ ...co, industry: e.target.value })} /></Field>
            <Field label={t("company_size")}><Select value={co.size} onChange={(v) => setCo({ ...co, size: v })} options={SIZES.map((x) => ({ value: x, label: x }))} /></Field>
            <Field label={t("company_loc")}><Input value={co.location} onChange={(e) => setCo({ ...co, location: e.target.value })} /></Field>
            <div className="sm:col-span-2"><Field label={t("company_about")}><Textarea value={co.about} onChange={(e) => setCo({ ...co, about: e.target.value })} /></Field></div>
          </div>
        )}
        <div className="mt-5 flex items-center gap-3">
          <Button onClick={save} busy={busy}>{t("save")}</Button>
          {msg && <span className="text-sm text-nile">{msg}</span>}
        </div>
        {error && <div className="mt-4"><ErrorNote>{error}</ErrorNote></div>}
      </Panel>
      {config?.supabase_url && (
        <Panel title={t("change_password")}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1"><Field label={t("new_password")} hint={t("password_hint")}><Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} minLength={8} autoComplete="new-password" /></Field></div>
            <Button variant="outline" disabled={pw.length < 8} onClick={changePw}>{t("change_password")}</Button>
          </div>
        </Panel>
      )}
    </div>
  );
}
