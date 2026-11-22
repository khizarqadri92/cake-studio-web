import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apost, aapi, refreshStaff, staff } from "./api";

export type StaffMe = { id: number; email: string; full_name: string; roles: string[]; permissions: string[] };
type Ctx = { me: StaffMe | null; ready: boolean; login(e: string, p: string): Promise<void>; logout(): Promise<void>; can(code: string): boolean };
const C = createContext<Ctx | null>(null);

export function StaffProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<StaffMe | null>(null);
  const [ready, setReady] = useState(false);
  const load = useCallback(async () => { try { setMe(await aapi<StaffMe>("/auth/me")); } catch { setMe(null); } }, []);
  useEffect(() => { (async () => { if (staff.hasRefresh && (await refreshStaff())) await load(); setReady(true); })(); }, [load]);
  const login = useCallback(async (email: string, password: string) => {
    const t = await apost<{ access_token: string; refresh_token: string }>("/auth/login", { email, password });
    staff.set(t.access_token, t.refresh_token);
    await load();
  }, [load]);
  const logout = useCallback(async () => {
    const rt = staff.rt(); staff.clear(); setMe(null);
    if (rt) { try { await apost("/auth/logout", { refresh_token: rt }); } catch { /* signed out locally */ } }
  }, []);
  // UI hint only: the server enforces permissions on every request.
  const can = useCallback((code: string) => !!me && (me.roles.includes("Super Admin") || me.permissions.includes(code)), [me]);
  const v = useMemo(() => ({ me, ready, login, logout, can }), [me, ready, login, logout, can]);
  return <C.Provider value={v}>{children}</C.Provider>;
}
export function useStaff() { const c = useContext(C); if (!c) throw new Error("useStaff outside StaffProvider"); return c; }
