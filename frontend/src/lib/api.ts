export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function detailMessage(d: unknown): string {
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => (e && typeof e === "object" && "msg" in e ? String((e as any).msg) : String(e))).join("; ");
  return "Something went wrong";
}

// Customer session. The short-lived access token lives only in memory; the refresh token is kept in
// localStorage so a reload keeps the customer signed in (trade-off documented in docs/SECURITY.md).
const RT_KEY = "cs_refresh";
let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;

export const session = {
  get access() { return accessToken; },
  get hasRefresh() { try { return !!localStorage.getItem(RT_KEY); } catch { return false; } },
  set(access: string, refresh: string) { accessToken = access; try { localStorage.setItem(RT_KEY, refresh); } catch { /* storage blocked */ } },
  clear() { accessToken = null; try { localStorage.removeItem(RT_KEY); } catch { /* storage blocked */ } },
  refreshToken() { try { return localStorage.getItem(RT_KEY); } catch { return null; } },
};

/** One refresh at a time: refresh tokens are single-use, so concurrent refreshes would sign the user out. */
export function refreshSession(): Promise<boolean> {
  const rt = session.refreshToken();
  if (!rt) return Promise.resolve(false);
  refreshing ??= (async () => {
    try {
      const r = await fetch("/api/v1/auth/customer/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }) });
      if (!r.ok) { if (r.status === 401) session.clear(); return false; }
      const t = await r.json();
      session.set(t.access_token, t.refresh_token);
      return true;
    } catch { return false; } finally { refreshing = null; }
  })();
  return refreshing;
}

export async function api<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...(init?.headers ?? {}) },
  });
  if (res.status === 401 && !retried && session.hasRefresh && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, init, true);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = detailMessage((await res.json()).detail ?? msg); } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const post = <T,>(path: string, body: unknown, headers?: Record<string, string>) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body), headers });
