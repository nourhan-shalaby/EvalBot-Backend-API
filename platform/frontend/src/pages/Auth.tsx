import { Building2, CheckCircle2, Eye, EyeOff, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LangSwitch, ThemeSwitch } from "../components/Shell";
import { Button, ErrorNote, Field, Input, Logo, Waveform } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type Kind = "candidate" | "company";

/** Brand panel shown beside the sign-in and sign-up forms on wide screens. */
function SidePanel({ kind, mode }: { kind: Kind; mode: "signin" | "signup" }) {
  const { t } = useI18n();
  const points = kind === "company" && mode === "signup"
    ? [t("side_c1"), t("side_c2"), t("side_c3")]
    : [t("side_p1"), t("side_p2"), t("side_p3")];
  return (
    <aside className="relative hidden flex-col justify-between overflow-hidden bg-ink p-10 text-paper lg:flex xl:p-14 dark:bg-sunken dark:text-ink">
      <Link to="/" aria-label="EvalBot home" className="[&_span]:!text-paper dark:[&_span]:!text-ink"><Logo size={32} /></Link>
      <div className="space-y-8">
        <div className="h-16 w-64"><Waveform bars={30} animated color="var(--color-amber)" /></div>
        <h2 className="max-w-md font-display text-4xl font-semibold leading-tight">
          {kind === "company" && mode === "signup" ? t("side_title_c") : t("side_title")}
        </h2>
        <ul className="max-w-md space-y-4">
          {points.map((p) => (
            <li key={p} className="flex items-start gap-3 text-[15px] leading-relaxed opacity-90">
              <CheckCircle2 size={20} className="mt-0.5 flex-none text-amber" /> {p}
            </li>
          ))}
        </ul>
      </div>
      <p className="max-w-md text-sm opacity-60">{t("footer_privacy")}</p>
    </aside>
  );
}

export default function Auth({ mode }: { mode: "signin" | "signup" }) {
  const { t } = useI18n();
  const { signIn, signUp, signInWithGoogle, resetPassword, config, refresh } = useAuth();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const next = params.get("next");
  const [kind, setKind] = useState<Kind>(params.get("as") === "company" ? "company" : "candidate");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const qs = (extra: Record<string, string> = {}) => {
    const p = new URLSearchParams({ ...(next ? { next } : {}), ...extra });
    const s = p.toString();
    return s ? `?${s}` : "";
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "signin") {
        await signIn(email, password);
        nav(next || "/app");
        return;
      }
      const r = await signUp(email, password, name);
      if (r.needsConfirmation) {
        setNotice(t("check_email"));
        return;
      }
      if (kind === "company") {
        await api.post("/companies", { name: company.trim() });
        await refresh();
        nav("/app");
      } else {
        await api.patch("/me", { role: "candidate" }).catch(() => undefined);
        await refresh();
        nav(next || "/app");
      }
    } catch (err: any) {
      setError(err?.message || t("error_generic"));
    } finally {
      setBusy(false);
    }
  };

  const forgot = async () => {
    if (!email) {
      setError(t("forgot_need_email"));
      return;
    }
    try {
      await resetPassword(email);
      setNotice(t("reset_sent"));
    } catch (err: any) {
      setError(err?.message || t("error_generic"));
    }
  };

  const tab = (to: "signin" | "signup", label: string) => (
    <Link to={`${to === "signin" ? "/login" : "/signup"}${qs(kind === "company" && to === "signup" ? { as: "company" } : {})}`} replace
      aria-current={mode === to ? "page" : undefined}
      className={`flex-1 rounded-lg px-4 py-2.5 text-center text-[15px] font-medium transition-colors ${mode === to ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"}`}>
      {label}
    </Link>
  );

  const kindCard = (k: Kind, Icon: typeof UserRound, title: string, desc: string) => (
    <button type="button" onClick={() => setKind(k)} aria-pressed={kind === k}
      className={`flex flex-1 items-start gap-3 rounded-xl border p-3.5 text-start transition-colors ${kind === k ? "border-nile bg-nile-soft" : "border-line bg-surface hover:border-nile"}`}>
      <Icon size={20} className={`mt-0.5 flex-none ${kind === k ? "text-nile" : "text-muted"}`} />
      <span>
        <span className={`block text-[15px] font-semibold ${kind === k ? "text-nile-deep" : "text-ink"}`}>{title}</span>
        <span className="mt-0.5 block text-xs text-muted">{desc}</span>
      </span>
    </button>
  );

  const disabled = config && !config.enabled;

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.1fr]">
      <SidePanel kind={kind} mode={mode} />
      <div className="flex flex-col">
        <header className="flex items-center justify-between px-5 py-4 sm:px-8">
          <Link to="/" className="lg:invisible" aria-label="EvalBot home"><Logo /></Link>
          <div className="flex items-center gap-1"><LangSwitch /><ThemeSwitch /></div>
        </header>
        <main className="flex flex-1 items-center justify-center px-5 pb-12 sm:px-8">
          <div className="w-full max-w-md">
            <div className="flex rounded-xl bg-sunken p-1" role="tablist" aria-label={t("auth_tabs")}>
              {tab("signin", t("sign_in"))}
              {tab("signup", t("sign_up"))}
            </div>

            <h1 className="mt-8 text-3xl font-semibold text-ink">{mode === "signin" ? t("auth_signin_title") : t("auth_signup_title")}</h1>
            <p className="mt-1.5 text-muted">{mode === "signin" ? t("auth_signin_sub") : t("auth_signup_sub")}</p>

            {disabled ? (
              <div className="mt-6 space-y-4">
                <p className="rounded-xl bg-amber-soft px-4 py-3 text-ink">{t("accounts_soon")}</p>
                <a href="/demo" className="inline-block rounded-xl bg-nile px-5 py-3 font-medium text-white dark:text-paper">{t("open_demo")}</a>
              </div>
            ) : notice ? (
              <p className="mt-6 rounded-xl bg-nile-soft px-4 py-3 text-nile-deep">{notice}</p>
            ) : (
              <form onSubmit={submit} className="mt-7 space-y-4">
                {mode === "signup" && (
                  <div>
                    <span className="mb-1.5 block text-sm font-medium text-ink">{t("account_type")}</span>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      {kindCard("candidate", UserRound, t("kind_candidate"), t("kind_candidate_d"))}
                      {kindCard("company", Building2, t("kind_company"), t("kind_company_d"))}
                    </div>
                  </div>
                )}
                {config?.supabase_url && config.providers?.google && (
                  <>
                    <Button type="button" variant="outline" className="w-full" onClick={() => signInWithGoogle().catch((e) => setError(e.message))}>
                      <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
                      {t("google")}
                    </Button>
                    <div className="flex items-center gap-3 text-sm text-muted"><span className="h-px flex-1 bg-line" />{t("or")}<span className="h-px flex-1 bg-line" /></div>
                  </>
                )}
                {mode === "signup" && (
                  <Field label={kind === "company" ? t("your_name") : t("full_name")}>
                    <Input value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
                  </Field>
                )}
                {mode === "signup" && kind === "company" && (
                  <Field label={t("company_name")}><Input value={company} onChange={(e) => setCompany(e.target.value)} required minLength={2} autoComplete="organization" /></Field>
                )}
                <Field label={kind === "company" && mode === "signup" ? t("work_email") : t("email")}>
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" dir="ltr" />
                </Field>
                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <label htmlFor="pw" className="text-sm font-medium text-ink">{t("password")}</label>
                    {mode === "signin" && config?.supabase_url && (
                      <button type="button" onClick={forgot} className="text-sm text-nile hover:underline">{t("forgot")}</button>
                    )}
                  </div>
                  <div className="relative">
                    <Input id="pw" type={showPw ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} required
                      minLength={mode === "signup" ? 8 : 1} autoComplete={mode === "signup" ? "new-password" : "current-password"} dir="ltr" className="pe-11" />
                    <button type="button" onClick={() => setShowPw((v) => !v)} aria-label={showPw ? t("hide_password") : t("show_password")}
                      className="absolute end-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-muted hover:text-ink">
                      {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  {mode === "signup" && <span className="mt-1 block text-xs text-muted">{t("password_hint")}</span>}
                </div>
                {error && <ErrorNote>{error}</ErrorNote>}
                <Button type="submit" busy={busy} className="w-full" size="lg">
                  {mode === "signin" ? t("sign_in") : kind === "company" ? t("create_company_account") : t("sign_up")}
                </Button>
              </form>
            )}

            <p className="mt-8 text-center text-sm text-muted">
              {mode === "signin" ? t("no_account") : t("have_account")}{" "}
              <Link to={`${mode === "signin" ? "/signup" : "/login"}${qs()}`} className="font-medium text-nile hover:underline">
                {mode === "signin" ? t("sign_up") : t("sign_in")}
              </Link>
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
