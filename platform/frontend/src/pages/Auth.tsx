import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/Shell";
import { Button, ErrorNote, Field, Input } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function Auth({ mode }: { mode: "signin" | "signup" }) {
  const { t } = useI18n();
  const { signIn, signUp, signInWithGoogle, resetPassword, config } = useAuth();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const next = params.get("next");
  const asCompany = params.get("as") === "company";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "signin") {
        await signIn(email, password);
        nav(next || "/app");
      } else {
        const r = await signUp(email, password, name);
        if (r.needsConfirmation) setNotice(t("check_email"));
        else nav(next || `/app/welcome${asCompany ? "?as=company" : ""}`);
      }
    } catch (err: any) {
      setError(err?.message || t("error_generic"));
    } finally {
      setBusy(false);
    }
  };

  const forgot = async () => {
    if (!email) {
      setError(t("email"));
      return;
    }
    try {
      await resetPassword(email);
      setNotice(t("reset_sent"));
    } catch (err: any) {
      setError(err?.message || t("error_generic"));
    }
  };

  return (
    <div className="min-h-screen">
      <PublicHeader />
      <main className="mx-auto max-w-md px-4 pb-16 pt-8">
        <h1 className="text-3xl font-semibold text-ink">{mode === "signin" ? t("auth_signin_title") : t("auth_signup_title")}</h1>
        {config && !config.enabled ? (
          <div className="mt-6 space-y-4">
            <p className="rounded-xl bg-amber-soft px-4 py-3 text-ink">{t("accounts_soon")}</p>
            <a href="/demo" className="inline-block rounded-xl bg-nile px-5 py-3 font-medium text-white dark:text-paper">{t("open_demo")}</a>
          </div>
        ) : notice ? (
          <p className="mt-6 rounded-xl bg-nile-soft px-4 py-3 text-nile-deep">{notice}</p>
        ) : (
          <form onSubmit={submit} className="mt-8 space-y-4">
            {config?.supabase_url && (
              <>
                <Button type="button" variant="outline" className="w-full" onClick={() => signInWithGoogle().catch((e) => setError(e.message))}>
                  <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
                  {t("google")}
                </Button>
                <div className="flex items-center gap-3 text-sm text-muted"><span className="h-px flex-1 bg-line" />{t("or")}<span className="h-px flex-1 bg-line" /></div>
              </>
            )}
            {mode === "signup" && (
              <Field label={t("full_name")}><Input value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" /></Field>
            )}
            <Field label={t("email")}><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></Field>
            <Field label={t("password")} hint={mode === "signup" ? t("password_hint") : undefined}>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === "signup" ? 8 : 1}
                autoComplete={mode === "signup" ? "new-password" : "current-password"} />
            </Field>
            {error && <ErrorNote>{error}</ErrorNote>}
            <Button type="submit" busy={busy} className="w-full" size="lg">{mode === "signin" ? t("sign_in") : t("sign_up")}</Button>
            {mode === "signin" && config?.supabase_url && (
              <button type="button" onClick={forgot} className="text-sm text-nile hover:underline">{t("forgot")}</button>
            )}
          </form>
        )}
        <p className="mt-8 text-sm text-muted">
          {mode === "signin" ? t("no_account") : t("have_account")}{" "}
          <Link to={`${mode === "signin" ? "/signup" : "/login"}${next ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-nile hover:underline">
            {mode === "signin" ? t("sign_up") : t("sign_in")}
          </Link>
        </p>
      </main>
    </div>
  );
}
