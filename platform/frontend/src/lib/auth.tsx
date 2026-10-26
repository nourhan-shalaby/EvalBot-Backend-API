import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Profile } from "./api";

type Config = { enabled: boolean; supabase_url: string; supabase_anon_key: string; dev_auth: boolean; calibrated_model: boolean; providers?: { google?: boolean } };

let supabase: SupabaseClient | null = null;
let config: Config | null = null;
const DEV_KEY = "evalbot_dev_token";

export async function loadConfig(): Promise<Config> {
  if (config) return config;
  const res = await fetch("/api/config");
  config = (await res.json()) as Config;
  if (config.supabase_url && config.supabase_anon_key) {
    supabase = createClient(config.supabase_url, config.supabase_anon_key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    });
  }
  return config;
}

export async function getAccessToken(): Promise<string | null> {
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session) return data.session.access_token;
  }
  try {
    return localStorage.getItem(DEV_KEY);
  } catch {
    return null;
  }
}

type AuthState = {
  ready: boolean;
  config: Config | null;
  profile: Profile | null;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name: string) => Promise<{ needsConfirmation: boolean }>;
  signInWithGoogle: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [cfg, setCfg] = useState<Config | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);

  const refresh = useCallback(async () => {
    const token = await getAccessToken();
    if (!token) {
      setProfile(null);
      return;
    }
    try {
      setProfile(await api.get<Profile>("/me"));
    } catch {
      setProfile(null);
    }
  }, []);

  useEffect(() => {
    let unsub: (() => void) | undefined;
    loadConfig()
      .then(async (c) => {
        setCfg(c);
        if (supabase) {
          const { data } = supabase.auth.onAuthStateChange(() => {
            refresh();
          });
          unsub = () => data.subscription.unsubscribe();
        }
        await refresh();
      })
      .finally(() => setReady(true));
    return () => unsub?.();
  }, [refresh]);

  const signIn = async (email: string, password: string) => {
    if (supabase) {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
    } else if (cfg?.dev_auth) {
      localStorage.setItem(DEV_KEY, `dev:${await devId(email)}:${email}`);
    }
    await refresh();
  };

  const signUp = async (email: string, password: string, name: string) => {
    if (supabase) {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: { full_name: name }, emailRedirectTo: `${location.origin}/app` },
      });
      if (error) throw error;
      if (!data.session) return { needsConfirmation: true };
    } else if (cfg?.dev_auth) {
      localStorage.setItem(DEV_KEY, `dev:${await devId(email)}:${email}`);
    }
    await refresh();
    if (name) await api.patch("/me", { full_name: name }).catch(() => undefined);
    await refresh();
    return { needsConfirmation: false };
  };

  const signInWithGoogle = async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: `${location.origin}/app` } });
    if (error) throw error;
  };

  const resetPassword = async (email: string) => {
    if (!supabase) return;
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${location.origin}/app/settings` });
    if (error) throw error;
  };

  const signOut = async () => {
    if (supabase) await supabase.auth.signOut();
    try {
      localStorage.removeItem(DEV_KEY);
    } catch {
      /* ignore */
    }
    setProfile(null);
  };

  return (
    <Ctx.Provider value={{ ready, config: cfg, profile, refresh, signIn, signUp, signInWithGoogle, resetPassword, signOut }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}

export async function updatePassword(password: string) {
  if (!supabase) return;
  const { error } = await supabase.auth.updateUser({ password });
  if (error) throw error;
}

/* stable pseudo-uuid from an email, for local development sign-in only */
async function devId(email: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email.toLowerCase()));
  const h = [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-a${h.slice(17, 20)}-${h.slice(20, 32)}`;
}
