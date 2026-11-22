import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, post, refreshSession, session } from "@/lib/api";

export type Address = { id: number; label: string; line: string; city: string; postal_code: string | null; instructions: string | null; is_default: boolean };
export type Me = { id: number; email: string; full_name: string; phone: string | null; email_verified: boolean; addresses: Address[] };

type Ctx = { me: Me | null; ready: boolean; login(email: string, password: string): Promise<void>; logout(): Promise<void>; reload(): Promise<void> };
const AuthCtx = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();

  const reload = useCallback(async () => {
    try { setMe(await api<Me>("/account/me")); } catch { setMe(null); }
  }, []);

  useEffect(() => {
    (async () => {
      if (session.hasRefresh && (await refreshSession())) await reload();
      setReady(true);
    })();
  }, [reload]);

  const login = useCallback(async (email: string, password: string) => {
    const t = await post<{ access_token: string; refresh_token: string }>("/auth/customer/login", { email, password });
    session.set(t.access_token, t.refresh_token);
    await reload();
  }, [reload]);

  const logout = useCallback(async () => {
    const rt = session.refreshToken();
    session.clear();
    setMe(null);
    qc.removeQueries({ queryKey: ["account"] });
    if (rt) { try { await post("/auth/customer/logout", { refresh_token: rt }); } catch { /* already signed out locally */ } }
  }, [qc]);

  const value = useMemo(() => ({ me, ready, login, logout, reload }), [me, ready, login, logout, reload]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): Ctx {
  const c = useContext(AuthCtx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
